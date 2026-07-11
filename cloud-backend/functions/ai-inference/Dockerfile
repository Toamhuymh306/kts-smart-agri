FROM public.ecr.aws/lambda/python:3.13

# Cài dependencies (torch CPU-only để giảm image size)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY app.py .

# Copy model weights vào subdirectory để Python's site.addsitedir
# không scan và đọc file .pth như Python path config file
RUN mkdir -p /var/task/models
COPY best_resnet_model.pth /var/task/models/best_resnet_model.pth
COPY best_lenet_model.pth /var/task/models/best_lenet_model.pth

# Lambda handler
CMD ["app.lambda_handler"]
