import logging
import os
import subprocess
from pathlib import Path
import sys
from lightning import LightningWork
from typing import Optional
from lightning.utilities.packaging.cloud_compute import CloudCompute

logger = logging.getLogger(__name__)


class JupyterWork(LightningWork):
    def __init__(self, host: str = "0.0.0.0", port: int = 8888, cloud_compute: Optional[CloudCompute] = None):
        super().__init__(exposed_ports={"jupyter": port}, cloud_compute=cloud_compute, blocking=False)
        self.host = host
        self.port = port
        self.pid = None
        self.token = None
        self.exit_code = None

    def run(self):

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

        with open(f"jupyter_lab_{self.port}", 'w') as f:
            proc = subprocess.Popen(
                f"{sys.executable} -m jupyter lab --ip {self.host} --port {self.port}".split(" "),
                bufsize=0,
                close_fds=True,
                stdout=f,
                stderr=f
            )

        with open(f"jupyter_lab_{self.port}", 'r') as f:
            while True:
                for line in f.readlines():
                    if "lab?token=" in line:
                        self.token = line.split("lab?token=")[-1]
                        proc.wait()



