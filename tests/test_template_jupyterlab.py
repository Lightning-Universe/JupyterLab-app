import os
from time import sleep
import playwright
from lightning import _PROJECT_ROOT
from lightning.testing.testing import run_app_in_cloud

def wait_for(page, callback):
    while True:
        try:
            res = callback()
            if res:
                return res
        except (playwright._impl._api_types.Error, playwright._impl._api_types.TimeoutError) as e:
            print(e)
            sleep(5)
            page.reload()
            sleep(2)

def test_template_jupyterlab_example_cloud():
    if os.getenv("TEST_APP_NAME", None):
        app_folder = os.path.join(_PROJECT_ROOT, "examples/template_jupyterlab")
    else:
        app_folder = os.path.dirname(os.path.dirname(__file__))
    with run_app_in_cloud(app_folder) as (_, view_page, _):
        def create_notebook():
            # 1. Locate the iframe
            iframe = view_page.frame_locator("iframe")
            # 2. Create a notebook
            button = iframe.locator('button:has-text("Create Jupyter Notebook")')
            button.wait_for(timeout=5 * 1000)
            button.click()
            return True

        wait_for(view_page, create_notebook)

        def wait_for_new_iframe():
            button = view_page.locator('button:has-text("JUPYTERLAB tchaton")')
            button.wait_for(timeout=5 * 1000)
            button.click()
            return True

        wait_for(view_page, wait_for_new_iframe)

        # 4. Open the jupyter lab tab
        iframe = view_page.frame_locator("iframe")
        found_jupyterlab = False
        for content in iframe.locator('div').all_text_contents():
            if "JupyterLab" in content:
                found_jupyterlab = True
        assert found_jupyterlab