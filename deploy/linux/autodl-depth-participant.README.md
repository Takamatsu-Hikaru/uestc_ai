# 无界杯：选手训练镜像（内置数据）

镜像内置本届固定版本的训练集1,995段、验证集466段，两组均覆盖40类。无需再次下载或解压44.6GB原始多模态数据。训练数据位于系统镜像内，创建实例后直接使用。

解释器：`/opt/uestc-classification/runtime/bin/python`。环境为Python3.12.3、PyTorch2.8.0+cu128、torchvision0.23.0+cu128、NumPy2.3.2、Pillow10.4.0、safetensors0.5.3。

## 开发目录

从官网题目页下载最新开发包 `wujie-classification-starter.zip`，上传到训练实例的 `/root/autodl-tmp`，执行：

```bash
mkdir -p /root/autodl-tmp/my-model
/opt/uestc-classification/runtime/bin/python -m zipfile -e \
  /root/autodl-tmp/wujie-classification-starter.zip /root/autodl-tmp/my-model
cd /root/autodl-tmp/my-model
```

在此目录修改 `network.py`、`train.py` 和 `inference.py`，新增模块可放入子目录。训练、预测和打包均使用此份工程。

## 训练与验证

```bash
/opt/uestc-classification/runtime/bin/python train.py \
  --training-data /opt/uestc-classification/training-data/train \
  --validation-data /opt/uestc-classification/training-data/validation \
  --epochs 10 --batch-size 8 --output model.safetensors

/opt/uestc-classification/runtime/bin/python predict.py \
  --dataset /opt/uestc-classification/training-data/validation \
  --output predictions.csv
```

训练逐轮显示耗时、损失和验证准确率。`predictions.csv` 的两列为 `sample_id,predicted_class`，类别编号为 0–39。模型结构、预处理与推理代码需保持一致。

## 作品打包

```bash
/opt/uestc-classification/runtime/bin/python build_classification_package.py \
  --project . --weights model.safetensors \
  --output /root/autodl-tmp/submission.zip
```

打包器读取 `--project` 中的配置、推理入口和 Python 模块，将训练权重保存为 `config.json` 的 `weights_file` 指定文件。附加词表、归一化参数等文件使用 `--include assets/normalization.json`，可重复指定。输出清单记录每个文件的 SHA-256，便于核对测试版本。

将 `submission.zip` 上传官网进行自测；正式提交补充训练代码、验证集预测 CSV 和技术路线说明。研究 PDF 可选。单个 ZIP 上限 20 MB，解压后上限 64 MB；较大权重使用题目说明中的 HTTPS 地址与 SHA-256 配置。

训练实例的数据和环境可以继续使用，开发包中的打包器替代旧镜像内的同名工具。

## 数据与预测接口

数据来自[CUHK-X官方仓库](https://huggingface.co/datasets/Kevin-Pal/CUHK-X_Small_Model_Track)，组织方已确认取得覆盖本届参赛队伍的数据分发授权，仅供本届授权参赛用途。请遵守数据授权并在报告中注明来源。

使用非RGB的伪彩色深度图，按帧序号排序后均匀取16帧，经Pillow亮度转换和112×112缩放，输出float32 `[16,1,112,112]` NPY，范围[0,1]，不代表物理距离。类别索引遵循 `/opt/uestc-classification/depth-class-mapping.csv`；训练、验证与测试被试互不重叠。

`Model(config, device).predict(sample_path)`必须返回40个有限数值。不得使用RGB、读取测试标签或自行填报比赛分数。组织方统一运行推理并生成指标；本届采用官方公开带标签数据重新划分，结合评委代码检查，不宣称严格独立盲测。

本镜像不包含组织方测试数据、测试标签、训练好的权重或平台/API密钥。不要向队伍挂载组织方共享文件存储；同一AutoDL账号的共享盘不能靠root权限隔离各队。
