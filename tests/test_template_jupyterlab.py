import os
from time import sleep
import playwright
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
    with run_app_in_cloud(os.path.dirname(os.path.dirname(__file__))) as (_, view_page, _):
        def create_notebook():
            # 1. Locate the iframe
            iframe = view_page.frame_locator("iframe")
            # 2. Create a notebook
            button = iframe.locator('button:has-text("Create Jupyter Notebook")')
            button.wait_for(timeout=5 * 1000)
            button.click()
            return True

        wait_for(view_page, create_notebook)

        # 3. Get the Jupyter Lab Token from the UI.
        def wait_for_token_available():
            iframe = view_page.frame_locator("iframe")
            pdiv = iframe.locator('p')
            contents = pdiv.all_text_contents()
            if len(contents) == 6 and contents[-1] not in ('None', 'False'):
                return pdiv.all_text_contents()[-1]

        token = wait_for(view_page, wait_for_token_available)

        def wait_for_new_iframe():
            button = view_page.locator('button:has-text("JUPYTERLAB 0")')
            button.wait_for(timeout=5 * 1000)
            button.click()
            return True

        wait_for(view_page, wait_for_new_iframe)

        # 4. Open the jupyter lab tab
        iframe = view_page.frame_locator("iframe")
        input_form = iframe.locator('text=Password or token: Log in >> input[name="password"]')
        input_form.wait_for(timeout=1 * 1000)
        input_form.fill(token)
        button = iframe.locator('button#login_submit')
        button.wait_for(timeout=1 * 1000)
        button.click()
        view_page.reload()
        sleep(5)
        divs = iframe.locator('div')
        divs.wait_for(timeout=1 * 1000)
        found_jupyterlab = False
        for content in iframe.locator('div').all_text_contents():
            if "JupyterLab" in content:
                found_jupyterlab = True
        assert found_jupyterlab