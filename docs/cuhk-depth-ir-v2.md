# A 题深度图＋IR 数据与运行环境

新版数据使用同步的伪彩深度图（RGB）和红外图（8 位灰度）。每段最多保留 32 帧，分辨率为 304×228，保留完整画面。训练集 1,995 段、验证集 466 段，类别顺序和人物划分沿用原版。实际下载大小、数据哈希和 baseline 成绩由发布产物记录。

## 数据下载与安装

公开目录提供 `dataset-index.json`、对应 SHA256、`train-000.zip` 等分卷及 `validation-000.zip` 等分卷。每个分卷最多包含 128 段；首分卷包含该集合的 `manifest.json` 和 `provenance.json`。索引中的 `archives[].file` 是相对于下载目录的 URL。索引不包含服务器路径、凭据或测试集。

```bash
python backend/install_classification_v2_shards.py \
  --index dataset-index.json --index-sha256 "$INDEX_SHA256" \
  --download-base-url "$DATA_DOWNLOAD_BASE_URL" --archives ./downloads \
  --split train --output ./data/compact-depth-ir-v1/train

python backend/install_classification_v2_shards.py \
  --index dataset-index.json --index-sha256 "$INDEX_SHA256" \
  --download-base-url "$DATA_DOWNLOAD_BASE_URL" --archives ./downloads \
  --split validation --output ./data/compact-depth-ir-v1/validation
```

已下载分卷会验证后复用。手工下载分卷后可省略 `--download-base-url`。安装器检查包大小、包哈希、清单哈希、片段哈希、帧号配对和图像格式，完整校验通过后才生成目标目录。

`manifest.json` 使用严格 v2 格式：顶层为 `version/classes/modality/samples`，每条样本为 `file/label/sha256`。`file` 指向包含 `Depth_Color/`、`IR/` 的目录。来源、原样本 ID 和采样方式放在 `provenance.json` 中。

## 开发包

使用公开预训练权重微调，R(2+1)D-34 是候选 baseline。人物裁剪使用 YOLO；分类器、检测器等全部推理模型合计不超过 100M 参数。最终取帧数、裁剪设置和实测成绩随选定的 baseline 发布。

`build_classification_v2_starter.py` 接收通过真实验证的导出目录，校验文件哈希后打包。包内包括本地权重、训练代码、数据安装器、预测和错例分析。旧版 `wujie-classification-starter.zip` 保持原样，新包使用独立版本文件名。

```bash
python backend/build_classification_v2_starter.py \
  --baseline "$VERIFIED_BASELINE_EXPORT" \
  --output ./public/downloads/wujie-classification-depth-ir-v2.zip
```

本地 `config.json` 使用 `weights_file: baseline.pt`。官网提交 ZIP 使用独立配置 `weights: {url, sha256, size}`，平台先下载固定权重，再将 `weights_path` 传给模型。较大的分类器权重不装入代码 ZIP。

## 推理与计分

接口仍为 `Model(config, device).predict(sample_path)`，返回 40 个有限分数。v2 的 `sample_path` 是当前片段目录；v1 仍传 NPY。评测器只暴露当前片段图像，目录名固定为 `clip`，帧名改为 `000000.png` 等序号。模型看不到清单、标签、人物编号或来源文件名。

项目成果沿用现有百分制：`0.80 × accuracy + 0.10 × macro_f1 + 0.10 × accuracy × min(1, 100 / latency_ms)`。首样本计入准确率，作为计时预热；之后计时包含选手图像读取、预处理、检测、分类和 CUDA 同步。数据向隔离目录的复制属于组织方准备时间。100 ms 参考值等待新版 baseline 在正式评测 GPU 的完整耗时测量，本次代码不改权重和阈值。

## 镜像与发布配置

训练与评测镜像使用相同 Python、PyTorch、torchvision、Pillow、NumPy 和 ultralytics 版本。`build_classification_image_manifest.py --profile depth-ir-v2` 将这些依赖及检测器依赖加入环境封存记录，worker 启动时逐项核验。

`autodl-depth-ir-v2-install.sh` 用于新的镜像构建实例：Python 3.10、PyTorch 2.5.1+cu118、torchvision 0.20.1+cu118、NumPy 2.2.6、Pillow 12.2.0、ultralytics 8.3.228、headless OpenCV 4.13.0.92，与本轮 baseline 的核心环境对齐。通过 `CLASSIFICATION_BASELINE_ZIP` 和 `CLASSIFICATION_BASELINE_SHA256` 安装已验证的开发包。脚本拒绝覆盖已有 runtime 和 starter，安装后保存完整依赖版本。

| 配置 | v2 发布要求 |
|---|---|
| 训练渠道 | 新建 provider，填写实际保存的训练镜像 UUID；已有实例的旧 provider 保留 |
| 评测镜像 | 安装 v2 数据读取与模型依赖，保存新镜像并恢复验收 |
| 数据版本 | 新 dataset ID 与固定 manifest SHA，旧 NPY 数据目录保留 |
| 题目 runtime | `execution=autodl-native`；镜像 UUID、dataset ID 和 SHA 与 JudgePool、worker 完全相同 |
| 历史提交 | 已有提交的题目禁止直接替换 runtime；使用 v2 草稿验收，切换入口时保留旧题与旧提交 |
| 静态文件 | 发布版本文件名；核对实际服务的 `dist/client/downloads` 与 `public/downloads` 哈希 |

新镜像 UUID、资源入口和最终成绩在发布验收时填写。数据、baseline、环境和题面作为同一个版本发布。

组织方最终测试集另行转换到相同的同步抽帧、分辨率和模态规范，使用 `prepare_depth_ir_dataset.py` 生成严格 v2 清单，再由 `install_classification_v2_data.py` 以包 SHA、manifest SHA 安装到私有版本目录。测试标签及来源清单只留在组织方；正式模型比较和调参使用公开验证集。测试集不装入学生下载包或训练镜像。

## 验收

本地测试覆盖分卷安装、严格清单校验、同步帧检查、匿名片段、独立 Python 选手进程读取图像、40 类预测和现有百分制计分；并保留旧 NPY 输入回归。Linux GPU 验收使用选定的真实 baseline，完成镜像恢复、全验证集预测、沙箱推理、计时与网站提交出分。

```bash
python -m unittest discover -s tests -p test_depth_ir_dataset.py -v
python -m unittest discover -s tests -p 'test_classification*.py' -v
```

真实模型的 Linux GPU 验收：

```bash
python backend/classification_v2_acceptance.py \
  --baseline "$VERIFIED_BASELINE_EXPORT" \
  --validation "$COMPACT_DATA/validation" \
  --gpu "$RESERVED_GPU_UUID" --samples 8 --output ./acceptance-v2
```

该命令使用实际 runner 的独立 UID、Landlock/seccomp、匿名输入与计时，保留推理日志、逐样本预测和计分结果。默认将本地权重暂存为只读文件，适用于权重尚未发布的实验验收；权重发布后加 `--weights-url`，同时验收 HTTPS 下载与 SHA 检查。沙箱解释器使用 `python -I`，依赖需安装在对应虚拟环境内，`PYTHONPATH` 不生效。小样本验收分数用于检查接口，完整验证集成绩另列。

多个验收并行时，分别设置 `--uid`，每个进程使用独立 GPU 和输出目录。YOLO、Matplotlib 与 XDG 配置缓存统一写入该次推理的 scratch 目录。

三个训练对照完成并选定 baseline 后，在已有 GPU reservation 中调用一次 `deploy/linux/cuhk-full-validation-acceptance.sh`：

```bash
bash deploy/linux/cuhk-full-validation-acceptance.sh \
  "$ISOLATED_PYTHON" "$PLATFORM_BACKEND" "$VERIFIED_BASELINE_EXPORT" \
  "$COMPACT_DATA/validation" "$AUDIT/deployment_predictions.npz" "$AUDIT/audit.json" \
  "$NEW_FULL_ACCEPTANCE_OUTPUT"
```

脚本要求 `CUDA_VISIBLE_DEVICES` 为已有单卡分配，使用全部 466 段公开验证集，不调度显卡、不训练。输出 `acceptance.json` 记录实际项目成果分、正确数、准确率、Macro F1 和平均推理耗时；`evidence.json` 保留逐片段预测与耗时。平均推理耗时含读取图像、预处理、检测、分类、CUDA 同步和进程通信，排除第一个预热片段；验收总耗时、judge 总耗时另列。

收集脚本先核对 FP32 审计中的权重 SHA 与预测文件 SHA，再按 `evidence.predictions[].file + '.npy'` 对齐 `deployment_predictions.npz` 的 `sample_ids`。`fp32-comparison.csv` 保存标签、平台预测、FP32 预测、是否一致和单段耗时；`full-validation-comparison.json` 保存差异样本列表与汇总。该流程验证公开验证集上的完整平台推理，生产镜像恢复、HTTPS 权重下载及网站提交验收分别记录。

## 参数量申报与复核

100M 上限适用于分类器、人物检测器及其他参与推理的模型，冻结参数也计入。提交材料列出各模型名称、参数量、权重来源与 SHA256、合计参数量，并提供加载同一提交权重的统计命令。PyTorch 模型可用 `sum(p.numel() for p in model.parameters())` 统计，逐个列出推理组件后汇总；训练时使用、推理时移除的教师模型单独说明。

当前执行方式是提交声明与组织方代码复核。评测 runner 检查输入、输出和运行资源；任意选手 `Model` 的参数量没有平台独立计数。baseline 中的自检和开发包 builder 的审计检查只覆盖该 baseline。

发布 v2 题目时，将 `docs/cuhk-depth-ir-v2-submission-fields.json` 中的字段合并进原 `submission_schema`，保留原有作品说明、附件和字段。现有接口会检查必填内容，参数总数由组织方复核。重点复核拟获奖队伍、接近上限及使用多模型的提交：检查推理入口实际加载的模型，用对应版本代码与权重执行统计，记录提交版本、各模型参数、合计、命令及复核人。

复核记录可保存在已有评审的 `feedback_md` 中。采用在线评审且设置了有权重评委的题目，可以让负责合规复核的评委先保存 `draft`，通过后提交评审；现有汇总逻辑只在全部有权重评委提交后产生总成绩。外部成绩占比 100% 的配置不使用此评审入口，应在导入确认成绩前完成复核。平台当前没有单独的“参数合规”状态；作品展示开关不控制排行榜。超限或材料不全的队伍补交合规版本后重新复核，组织方据已复核版本确认最终成绩。
