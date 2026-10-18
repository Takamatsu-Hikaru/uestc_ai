# CUHK A 题 v2 发布清单

## 当前状态

| 项目 | 修改范围 | 已有验证 | 剩余验收 |
|---|---|---|---|
| 赛题说明 | 输入模态、公开预训练微调、100元资源、交付、评分与声明 | 候选题面及计分条款已准备，Opus完成两轮设计复核 | 填入最终baseline、参考值和下载入口 |
| 学生数据 | 1995训练＋466验证，深度/IR同步32帧上限、304×228，单个ZIP 4.90GB | ZIP完整性、清单、配对与安装通过 | 上传固定下载地址，核对线上文件 |
| 运行环境 | 学生使用Python环境安装脚本；组织方使用原生分类worker，更新图像读取和权重加载 | 环境构建脚本、读取与隔离接口检查已准备 | 新镜像保存/恢复、实际GPU训练与推理 |
| baseline | 16帧公开预训练微调，提供训练/验证/错例/预览 | 代码包已准备；提交工具在Python3.10实测通过 | 一份新数据实测权重、成绩与成本 |
| rubric | 项目100分：60基准＋20提升＋10类别表现＋10效率 | 公式、边界与API自动取分测试通过 | 固定B/G/T；保持阶段内部80/20、总成绩60/40 |
| 测评系统 | 匿名双模态输入、私有权重、470段组织方测试、3次自测和正式选分 | 本地真实API/数据库流程通过；PR前后端CI通过 | 新版470段数据安装、实际大权重HTTPS＋GPU自测出分 |

本次学生交付为数据 ZIP 和 Python 开发包；组织方测评环境按下表部署。接口验证与 GPU 出分分别登记。发布实验保留一份baseline的训练→验证→分析→提交记录即可，全面消融另行开展。

## 版本变化

| 内容 | 现官网 v1 | v2 候选 |
|---|---|---|
| 输入 | 单模态灰度深度，16帧112×112，NPY | 同步伪彩深度＋IR，最多32对帧304×228，图像目录 |
| 数据划分 | 1995训练／466验证／470组织方测试 | 保持样本与跨人物划分，更新输入格式 |
| 学习主线 | 从头训练，限制RGB预训练特征 | 推荐公开预训练模型微调；从零训练可选 |
| 学生数据 | 训练镜像中的旧预处理数据 | 单个4.90GB数据ZIP，解压得到train/validation |
| baseline | 旧灰度实验记录 | 选定一份简单16帧微调方案，发布实测权重、代码、预测与成本 |
| 算力资源 | 每队10 GPU小时／约16.8元 | 每队100元AutoDL算力券 |
| 权重提交 | 代码ZIP＋外部HTTPS大权重 | 增加队伍私有分块上传，代码引用冻结权重 |
| 本地验证 | 模型自行测试 | 加本地包检查、预测、错例、同步帧预览 |
| 官网自测 | 每队3次、1800秒 | 保持；正式提交选择一次已完成且同包同权重的结果 |
| 项目成果 | 80%准确率＋10%F1＋10%准确率加权效率 | 候选：基准60＋提升20＋类别表现10＋效率10 |
| 阶段权重 | 第一阶段50%／答辩50% | 第一阶段60%／答辩40%；阶段内部项目80%／说明20% |
| 版本切换 | 旧NPY runtime | 新题草稿、新provider、新runtime，旧提交保留 |

## 发布内容与修改位置

| 交付 | 对应文件或位置 | 完成条件 |
|---|---|---|
| 官网题面 | `backend/competitions/wujie-cup-2026/classification-depth-ir-v2.md` | 从草稿导入新题，核对数据/微调/资源/提交/成绩 |
| 计分说明 | `docs/cuhk-depth-ir-v2-scoring.md` | 填入实测B、G、T、baseline SHA与评测硬件 |
| 计分函数 | `backend/platform_api/performance_scoring.py` | 新preset显式启用，规则和自测快照一致 |
| 分数展示 | `app/components/EvaluationMetrics.tsx`、`app/lib/domain.ts` | 项目分及四项分值、分类整体指标显示正确 |
| 数据安装 | `backend/install_classification_v2_shards.py` | 全部分卷/样本/模态同步校验通过 |
| 私有测试数据 | `backend/prepare_depth_ir_dataset.py`、`backend/install_classification_v2_data.py` | 转换470段，安装新dataset ID，留存manifest SHA |
| 最终开发包 | `backend/build_classification_v2_starter.py` | 接受选定baseline的真实审计导出，生成版本化ZIP |
| 训练/评测镜像 | `deploy/linux/autodl-depth-ir-v2-install.sh`、`backend/build_classification_image_manifest.py` | 保存并恢复镜像，实际GPU上完成推理 |
| GPU验收 | `backend/classification_v2_acceptance.py`、`deploy/linux/cuhk-full-validation-acceptance.sh` | 全466预测与导出逐项对应，记录完整pipeline成本 |
| 权重上传 | `backend/platform_api/routes/model_weights.py`、`backend/upload_classification_weights.py` | 权限、额度、SHA、冻结引用、真实大文件传输 |
| 推理/权重加载 | `backend/classification_worker.py`、`backend/evaluation_adapters/classification_runner.py` | 同一租约读取冻结资产，匿名数据输入、40类输出 |
| 提交检查 | `backend/check_classification_submission.py` | 本地检查代码ZIP、配置与权重引用，不消耗自测 |
| 数据库迁移 | `backend/migrations/versions/f18c20261018_private_model_weights.py` | 在预发布数据库执行迁移、回归原提交 |
| 自动化验收 | `tests/test_classification_baseline_scoring.py`、`test_baseline_scoring_api.py`、`test_classification_v2_submission_api.py`、`test_classification_weight_upload.py` | 公式、真实API/DB、权限、次数与版本快照通过 |

## 学生流程

| 环节 | 学生操作 | 可见结果 |
|---|---|---|
| 下载 | 获取数据ZIP和开发包，解压数据 | 已校验的训练/验证集与数据预览 |
| 环境 | 运行开发包setup.sh安装Python/PyTorch环境 | 可载入图像、预训练权重与baseline |
| 验证 | 运行已提供baseline | 公开验证集指标、预测文件与错例 |
| 微调 | 修改采样、裁剪、融合或训练参数 | 新权重、训练记录与同集合比较 |
| 分析 | 打开错例和同步帧预览 | 具体动作混淆、失败片段和下一次改动依据 |
| 提交检查 | 上传私有权重，打包推理代码，执行本地检查 | SHA固定的权重引用与可提交代码包 |
| 自测 | 官网发起自测 | 组织方测试集指标、项目成果分、剩余次数 |
| 正式提交 | 选择已完成结果，补齐技术说明与复现材料 | 固定的作品版本与第一阶段评审材料 |

## 最小实验范围

发布前完成一份选定baseline的新数据微调、全验证集预测、训练时间与显存记录、评测环境推理成本，以及同一作品的上传→自测→正式提交。确认100元资源可以覆盖基线复现和后续多次小规模修改，并列出单次预计费用与实际运行时间。

baseline选型优先简单、稳定、易复现，期望准确率约60–70%，按实测结果发布。其余架构、32帧、裁剪和模态消融属于后续对照；不要求达到90%才能发布。

## 发布验收

- [ ] 新版470段测试数据完成转换、私有安装与SHA核验。
- [ ] 选定baseline完成一次新数据训练，权重、预测、时间、显存与成本已归档。
- [ ] 同一权重完成全466验证和正式环境测试，填入B；按统一硬件测得T并固定G。
- [ ] 版本化开发包包含baseline权重、微调与推理代码、检查器、分析工具和实测README。
- [ ] 新训练/测评镜像实际保存、恢复并在目标GPU验收，登记镜像标识与依赖版本。
- [ ] 数据ZIP、开发包及指南的实际下载链接校验成功。
- [ ] 基线大权重通过正式入口上传、引用、自测、正式选分与评委取分。
- [ ] 用新题草稿核对100元资源、3次自测、1800秒、80/20和60/40配置。
- [ ] 规则参考值在开放自测前固定；旧题旧提交仍使用原runtime与原计分版本。
- [ ] 负责人确认发布配置后切换题目入口。

以上方框记录发布验收，不代表本地代码测试未完成。当前实测证据和交付状态单独登记，日期到达不自动勾选。
