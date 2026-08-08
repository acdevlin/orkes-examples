from conductor.client.automator.task_handler import TaskHandler
from conductor.client.configuration.configuration import Configuration
from conductor.client.orkes_clients import OrkesClients
from conductor.client.workflow.conductor_workflow import ConductorWorkflow
from conductor.client.worker.worker_task import worker_task
from conductor.client.configuration.settings.authentication_settings import AuthenticationSettings

import os

@worker_task(task_definition_name='greet', register_task_def=True)
def greet(name: str) -> str:
    return f'Hello {name}'


def main():
    config = Configuration(
      base_url='https://developer.orkescloud.com', 
      authentication_settings=AuthenticationSettings(
        key_id=os.environ.get('ORKES_API_KEY', None),
        key_secret=os.environ.get('ORKES_API_SECRET', None)))
    clients = OrkesClients(configuration=config)
    executor = clients.get_workflow_executor()

    workflow = ConductorWorkflow(name='greetings', version=1, executor=executor)
    greet_task = greet(task_ref_name='greet_ref', name=workflow.input('name'))
    workflow >> greet_task
    workflow.output_parameters({'result': greet_task.output('result')})
    workflow.register(overwrite=True)

    with TaskHandler(configuration=config, scan_for_annotated_workers=True) as task_handler:
        task_handler.start_processes()
        run = executor.execute(
            name='greetings', 
            version=1, 
            workflow_input={'name': 'Conductor'})
        print(f'Result: {run.output["result"]}')
        print(f'Execution: {config.ui_host}/execution/{run.workflow_id}')


if __name__ == '__main__':
    main()