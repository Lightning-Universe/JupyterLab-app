import lightning as L
from lightning.components.python import JupyterLabWork

class JupyterLabManager(L.LightningFlow):

    def __init__(self):
        super().__init__()
        self.notebooks_session = L.structures.Dict()
        self.user_notebook_configs = []

    def run(self):
        for idx, jupyter_config in enumerate(self.user_notebook_configs):
            username = jupyter_config["username"]
            if username not in self.notebooks_session:
                jupyter_config["ready"] = False
                accelerator = "gpu" if jupyter_config["use_gpu"] else "cpu"
                self.notebooks_session[username] = JupyterLabWork(cloud_compute=L.CloudCompute(accelerator, 1))
            self.notebooks_session[username].run()

            if self.notebooks_session[username].token:
                jupyter_config["token"] = self.notebooks_session[username].token

            if jupyter_config['stop']:
                self.notebooks_session[username].stop()
                self.user_notebook_configs.pop(idx)

    def configure_layout(self):
        return L.frontend.StreamlitFrontend(render_fn=render_fn)

def render_fn(state):
    import streamlit as st

    st.set_page_config(layout="wide")

    col1, col2, col3 = st.columns(3)
    with col1:
       create_jupyter = st.button("Create Jupyter Notebook")
    with col2:
        username = st.text_input('Enter your username', "tchaton")
        assert username
    with col3:
        use_gpu = st.checkbox('Use GPU')

    if create_jupyter:
        state.user_notebook_configs = state.user_notebook_configs + [{"use_gpu": use_gpu, "token": None, "username": username, "stop": False}]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"Idx")
    with col2:
        st.write(f"Use GPU")
    with col3:
        st.write(f"Stop")

    for idx, config in enumerate(state.user_notebook_configs):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"{idx}")
        with col2:
            st.write(config['use_gpu'])
        with col3:
            if config["token"]:
                should_stop = st.button("Do you want to stop the notebook")
                if should_stop:
                    config["stop"] = should_stop
                    state.user_notebook_configs = state.user_notebook_configs

class RootFlow(L.LightningFlow):

    def __init__(self):
        super().__init__()
        self.manager = JupyterLabManager()

    def run(self):
        self.manager.run()

    def configure_layout(self):
        layout = [{"name": "Manager", "content": self.manager}]
        for config in self.manager.user_notebook_configs:
            if not config['stop']:
                username = config['username']
                jupyter_work = self.manager.notebooks_session[username]
                layout.append(
                    {"name": f"JupyterLab {username}", "content": jupyter_work.url + "/lab"}
                )
        return layout


app = L.LightningApp(RootFlow())
