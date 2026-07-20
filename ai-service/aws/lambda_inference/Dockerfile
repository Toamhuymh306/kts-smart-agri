FROM public.ecr.aws/lambda/python:3.11

COPY aws/lambda_inference/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt --target ${LAMBDA_TASK_ROOT}

COPY aws/lambda_inference/handler.py ${LAMBDA_TASK_ROOT}/handler.py
COPY aws/lambda_inference/runtime.py ${LAMBDA_TASK_ROOT}/runtime.py
COPY aws/lambda_inference/model/ ${LAMBDA_TASK_ROOT}/model/
COPY best_resnet_model.pth ${LAMBDA_TASK_ROOT}/model/best_resnet_model.pth

CMD ["handler.lambda_handler"]
