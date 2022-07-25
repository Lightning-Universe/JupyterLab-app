from collections import defaultdict
from lightning.app.storage import Path
from lightning.app.structures import Dict
from lightning import CloudCompute, LightningApp, LightningFlow, LightningWork
from lightning.app.frontend import StreamlitFrontend
import os
import re
import subprocess
import sys
from typing import Callable, List, Optional, TypedDict, Type
import time
import json
from lightning_cloud.openapi.rest import ApiException

from dataclasses import dataclass, asdict


class JupyterLabWork(LightningWork):
    def __init__(self, username: str, accelerator_type: str):
        super().__init__(cloud_compute=CloudCompute(accelerator_type), parallel=True)
        self.username = username
        self.accelerator_type = accelerator_type
        self.pid = None
        self.token = None
        self.exit_code = None
        self.storage = None
        self.events = []

    def run(self):
        self.storage = Path(".")

        jupyter_notebook_config_path = Path.home() / ".jupyter/jupyter_notebook_config.py"

        if os.path.exists(jupyter_notebook_config_path):
            os.remove(jupyter_notebook_config_path)

        with subprocess.Popen(
            f"{sys.executable} -m notebook --generate-config".split(" "),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            close_fds=True,
        ) as proc:
            self.pid = proc.pid

            self.exit_code = proc.wait()
            if self.exit_code != 0:
                raise Exception(self.exit_code)

        with open(jupyter_notebook_config_path, "a") as f:
            f.write(
                """c.NotebookApp.tornado_settings = {'headers': {'Content-Security-Policy': "frame-ancestors * 'self' "}}"""  # noqa E501
            )

        with open(f"jupyter_lab_{self.port}", "w") as f:
            proc = subprocess.Popen(
                f"{sys.executable} -m jupyter lab --ip {self.host} --port {self.port} --no-browser --config={jupyter_notebook_config_path}".split(" "),
                bufsize=0,
                close_fds=True,
                stdout=f,
                stderr=f,
            )


        with open(f"jupyter_lab_{self.port}") as f:
            while True:
                for line in f.readlines():
                    if "lab?token=" in line:
                        self.token = line.split("lab?token=")[-1]

                        # Publish event for all !
                        PubSubLightningFlow.publish(self, NotebookReadyEvent(username=self.username))

                        proc.wait()

    @property
    def url(self):
        if not self.token:
            return ""
        if self._future_url:
            return f"{self._future_url}/lab?token={self.token}"
        else:
            return f"http://{self.host}:{self.port}/lab?token={self.token}"


@dataclass
class Event:
    name: Optional[str] = None
    ts: Optional[float] = None

    def __post_init__(self):
        self.name = self.name or self.__class__.__name__
        self.ts = self.ts or time.time()


@dataclass
class NotebookCreationRequestedEvent(Event):
    username: str = None
    accelerator_type: str = None


@dataclass
class NotebookStopRequestedEvent(Event):
    username: str = None


@dataclass
class NotebookReadyEvent(Event):
    username: str = None


class NotebookStatus(TypedDict):
    accelerator_type: str
    status: bool
    message: Optional[str]


accelerator_types = [
    'default',
    'cpu-small',
    'cpu-medium',
    'gpu',
    'gpu-fast',
    'gpu-fast-multi',
]


class PubSubLightningFlow(LightningFlow):
    # This is sort-of experimental way of handling what's happening in the app
    # I think that some apps might benefit from that - Probably we should think
    #    if that's something we could incorporate directly into framework. 

    # CAUTION: Atm we can only subscribe to class method, ordinary method will fail
    #            due to fact we use __getattr__()

    def __init__(self):
        super().__init__()
        self.subscriptions = defaultdict(list)
        self.events = []

    def subscribe(self, event: Type[Event], method: Callable):
        self.subscriptions[event.__name__].append(method.__name__)
        self.subscriptions = self.subscriptions  # Force state update

    def unsubscribe(self, event: Event, method: Callable):
        self.subscriptions[event.__name__].remove(method.__name__)
        self.subscriptions = self.subscriptions  # Force state update

    def publish(self, event: Event):
        self.events += [asdict(event)]

    def run(self):

        for work in self.works():
            if hasattr(work, "events"):
                self.events.extend(work.events)
                work.events = []

        events: List[Event] = [globals()[e["name"]](**e) for e in self.events]

        for event in events:
            for subscriber in self.subscriptions[event.name]:
                self.__getattr__(subscriber)(event)

        # Will this discard events for all other components? Or just this one?
        #   need to test that
        self.events = []


class JupyterLabManager(PubSubLightningFlow):

    def __init__(self):
        super().__init__()
        self.jupyter_works = Dict()
        self.configs = {}

        self.subscribe(NotebookCreationRequestedEvent, self.on_create_request)
        self.subscribe(NotebookStopRequestedEvent, self.on_stop_request)
        self.subscribe(NotebookReadyEvent, self.on_ready)

    def on_create_request(self, event: NotebookCreationRequestedEvent) -> None:

        print("on_create_request:", event)

        try:
            print(f"Creating new Notebook for {event.username} with {event.accelerator_type} compute resource")

            # 1. Create new config
            # We need this oconfig because stremlit does cannot reach works from state ;(
            self.configs[event.username] = NotebookStatus(accelerator_type=event.accelerator_type, status="Creating", message="")
            self.configs = self.configs

            # raise ApiException("Dupa")

            # 2. Create new work
            self.jupyter_works[event.username] = JupyterLabWork(accelerator_type=event.accelerator_type, username=event.username)
            self.jupyter_works[event.username].run()

        except ApiException as e:
            # Quota errors
            print("Exception while creating Notebook for {event.username}:", str(e))

            self.configs[event.username]["status"] = "Error"
            self.configs[event.username]["message"] = json.loads(e.body).get("message")
            self.configs = self.configs

    def on_stop_request(self, event: NotebookStopRequestedEvent) -> None:
        print("on_stop_request", event)

        try:
            self.jupyter_works[event.username].stop()
            del self.jupyter_works[event.username]
            del self.configs[event.username]
            self.configs = self.configs
        
        except Exception as e:
            print(str(e))
            print("Exception ^")
        # del self.jupyter_works[event.username]

    def on_ready(self, event: NotebookReadyEvent) -> None:
        print("on_ready:", event)

        self.configs[event.username]["status"] = "Running"
        self.configs = self.configs

    def configure_layout(self):
        return StreamlitFrontend(render_fn=render_fn)

def render_fn(state):
    import streamlit as st

    # Step 1: Enable users to select their notebooks and create them
    col1, col2, col3 = st.columns(3)
    with col1:
        create_jupyter = st.button("Create Jupyter Notebook")
    with col2:
        username = st.text_input('Enter your name', "tchaton")
        assert username
    with col3:
        accelerator = st.selectbox('Select accelerator', accelerator_types)

    # Step 2: If a user clicked the button, add an element to the list of configs
    # Note: state.jupyter_configs = ... will sent the state update to the component.
    if create_jupyter:
        # Make username url friendly
        username = re.sub("[^0-9a-zA-Z]+", "_", username)
        PubSubLightningFlow.publish(state, NotebookCreationRequestedEvent(username=username, accelerator_type=accelerator))

    # Step 3: List of running notebooks.
    for idx, (username, config) in enumerate(state.configs.items()):

        col1, col2, col3, col4 = st.columns([1, 1, 3, 1])
        with col1:
            if not idx:
                st.markdown(f"#### Username")
            st.write(username)
        
        with col2:
            if not idx:
                st.markdown(f"#### Accelerator")
            st.write(config["accelerator_type"])
        
        with col3:
            if not idx:
                st.markdown(f"#### Status")

            status = config["status"]

            if status == "Running":
                st.success(status)
            
            if status == "Creating":
                st.info(status)
            
            if status == "Error":
                st.error(config["message"])

        with col4:
            if not idx:
                # st.markdown(f"*Action*")
                st.markdown("#### Action")

            if config["status"] == "Running":
                if st.button("Stop this Notebook", key=str(idx)):
                    PubSubLightningFlow.publish(state, NotebookStopRequestedEvent(username=username))
        
            if config["status"] == "Error":
                if st.button("Restart this Notebook", key=str(idx+1)):
                    PubSubLightningFlow.publish(state, NotebookCreationRequestedEvent(username=username, accelerator_type=config["accelerator_type"]))
                
                if st.button("Delete this Notebook", key=str(idx+2)):
                    PubSubLightningFlow.publish(state, NotebookStopRequestedEvent(username=username))
                


class RootFlow(LightningFlow):

    def __init__(self):
        super().__init__()
        self.manager = JupyterLabManager()

    def run(self):
        self.manager.run()

    def configure_layout(self):
        layout = [{"name": "Manager", "content": self.manager}]
        for username, config in self.manager.configs.items():
            if config["status"] == "Running":
                layout.append(
                    {"name": f"JupyterLab {username}", "content": self.manager.jupyter_works[username]}
                )
        return layout


app = LightningApp(RootFlow())
