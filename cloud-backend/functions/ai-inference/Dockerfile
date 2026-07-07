FROM public.ecr.aws/lambda/python:3.11

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY app.py .

# Lambda handler
CMD ["app.lambda_handler"]
