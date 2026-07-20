# AI Service

The Lambda inference runtime is deployed as a Docker image from `aws/`. The two
checked-in `.pth` files are PyTorch state dictionaries, not TorchScript files:

- `best_resnet_model.pth`: ResNet-50, 38 output classes (default)
- `best_lenet_model.pth`: project LeNet variant, 38 output classes

Select the checkpoint with `MODEL_NAME=resnet` or `MODEL_NAME=lenet`. The Docker
build copies both checkpoints and preprocessing metadata into
`${LAMBDA_TASK_ROOT}/model`.

Local inference:

```powershell
./.venv/Scripts/python.exe test_model_local.py <sample-image> --model resnet
./.venv/Scripts/python.exe test_model_local.py <sample-image> --model lenet
```

Build and deploy instructions are in `../DEPLOYMENT_FIXES.md` and
`aws/deploy_lambda_container.ps1`.
