import os
from tests_app import _PROJECT_ROOT
from lightning.app.testing.testing import run_app_in_cloud, wait_for


def test_template_jupyterlab_example_cloud():
    if os.getenv("TEST_APP_NAME", None):
        app_folder = os.path.join(_PROJECT_ROOT, "examples/app_template_jupyterlab")
    else:
        app_folder = os.path.dirname(os.path.dirname(__file__))
    with run_app_in_cloud(app_folder) as (_, view_page, _):
        def create_notebook(*_, **__):
            # 1. Locate the iframe
            iframe = view_page.frame_locator("iframe")
            # 2. Create a notebook
            button = iframe.locator('button:has-text("Create Jupyter Notebook")')
            button.wait_for(timeout=5 * 1000)
            button.click()
            return True

        wait_for(view_page, create_notebook)

        def wait_for_new_iframe(*_, **__):
            button = view_page.locator('button:has-text("JUPYTERLAB TCHATON")')
            button.wait_for(timeout=5 * 1000)
            button.click()
            return True

        wait_for(view_page, wait_for_new_iframe)

        def found_jupyterlab(*_, **__):
            # 4. Open the jupyter lab tab
            iframe = view_page.frame_locator("iframe")
            div = iframe.locator('div >> nth=0')
            div.wait_for(timeout=10 * 1000)
            found_jupyterlab = False
            for content in iframe.locator('div').all_text_contents():
                if "JupyterLab" in content:
                    found_jupyterlab = True
            return found_jupyterlab

        wait_for(view_page, found_jupyterlab)