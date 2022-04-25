from typing import Dict, List
from lightning.utilities.packaging.cloud_compute import CloudCompute
from jupyter_work import JupyterWork
from lightning.frontend import StreamlitFrontend
from lightning import LightningApp, LightningFlow
from lightning.utilities.state import AppState
from lightning.utilities.network import find_free_network_port


class JupyterLabManager(LightningFlow):

    def __init__(self):
        super().__init__()
        self.jupyter_configs = []

    def run(self):
        for jupyter_idx, jupyter_config in enumerate(self.jupyter_configs):
            name = f"jupyter_work_{jupyter_idx}"
            if not hasattr(self, name):
                jupyter_config["ready"] = False
                accelerator = "gpu" if jupyter_config["use_gpu"] else "cpu"
                setattr(self, name, JupyterWork(cloud_compute=CloudCompute(accelerator, 1), port=find_free_network_port()))
            jupyter_work = getattr(self, name)
            jupyter_work.run()
            if jupyter_work.token:
                jupyter_config["token"] = jupyter_work.token


    def configure_layout(self):
        return StreamlitFrontend(render_fn=render_fn)

def render_fn(state: AppState):
    import streamlit as st
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(interval=1000, limit=None, key="refresh")

    col1, col2 = st.columns(2)
    with col1:
       create_jupyter = st.button("Create Jupyter Notebook")
    with col2:
        use_gpu = st.checkbox('Use GPU')

    if create_jupyter:
        state.jupyter_configs = state.jupyter_configs + [{"use_gpu": use_gpu, "token": None}]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"Idx")
    with col2:
        st.write(f"Use GPU")
    with col3:
        st.write(f"Token")

    for idx, config in enumerate(state.jupyter_configs):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"{idx}")
        with col2:
            st.write(config['use_gpu'])
        with col3:
            st.write(config["token"])


class RootFlow(LightningFlow):

    def __init__(self):
        super().__init__()
        self.manager = JupyterLabManager()

    def run(self):
        self.manager.run()

    def configure_layout(self) -> List[Dict]:
        layout = [{"name": "Manager", "content": self.manager}]
        for idx, work in enumerate(self.manager.works()):
            jupyter_url = work.exposed_url("jupyter")
            jupyter_url = jupyter_url + "/lab" if jupyter_url else jupyter_url
            layout.append(
                {"name": f"JupyterLab {idx}", "content": jupyter_url}
            )
        return layout


app = LightningApp(RootFlow())
