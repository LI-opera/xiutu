# ADR 0002：本地 E5-small FP32 ONNX

日期：2026-09-18。选择仅用于WP-05，等待本包审核。

本机 Ryzen 5 7500F（6核12线程）、约31.65GiB RAM、RTX4060 8188MiB；未发现可直接复用的Hugging Face模型缓存。采用CPU推理，避免将CUDA驱动组合和GPU显存竞争引入本包。BGE-M3为候选（长上下文/多语言），本轮没有下载或性能实测它，不能据此断言它不适合本机。先实测较小的多语言E5作为可用基线；未来比较更大模型属于另行选择，不覆盖本次留出集结果。

选择[官方 multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)，固定revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`，官方仓库标记MIT。使用该revision的`onnx/model.onnx`（470268510字节）和`onnx/tokenizer.json`，SHA256固化于EmbeddingGateway及model-manifest.json。没有加载远程Python或PyTorch pickle，没有外部推理请求；只下载公开模型，不上传资料。模型文件在被忽略的`.local-data/models/`，不加入Git。

E5使用query/passage前缀、mean pooling及归一化。本项目文档前缀准确为`passage: `，查询为`query: `。长chunk可能超过模型512长度，因此使用480内容token不重叠窗口，每窗加前缀/特殊token，窗内attention mean→L2、按内容token数量加权合并→L2；最大输入不超过512。此扩展是本项目策略，不宣称与原作者长文本评测等价。固定384维，不对外开放任意模型名/动态维度。

实测证据 model-probe-v2.json：加载1.628秒；3条文档约18.75ms、3条查询约11.90ms；进程工作集802103296字节，峰值1181065216字节。包含运行时/词表/模型，不是仅权重大小，不是并发性能保证。首轮内存API句柄类型错误返回0，原model-probe.json保留；v2修正句柄类型后另测，没有覆盖原结果。

中文失火/水温调试查询正确指向对应段落；中文亏电查询未把英文电瓶段落排第一，此负例保留。没有基于留出查询调整模型、分词或排序。冻结24段合成语料、12条查询后，baseline Recall@5=0.8472，hybrid=0.9306；Hit@5=.9167/1.0，MRR@10=.8611/.8819；q11、q12仍有不完整召回。合成标签由实施者编写，不是人工维修真值；跨语言和真实车型召回尚未获证实。

运行时为[ONNX Runtime CPU](https://onnxruntime.ai/docs/get-started/with-python.html)（1.30.0，MIT）、[Hugging Face Tokenizers](https://huggingface.co/docs/tokenizers/api/tokenizer)（0.23.2，Apache-2.0）、NumPy（2.5.3，BSD-3-Clause）。许可核对：[ORT](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)、[Tokenizers](https://github.com/huggingface/tokenizers/blob/main/LICENSE)、[NumPy](https://github.com/numpy/numpy/blob/main/LICENSE.txt)。uv.lock为依赖真相，requirements由锁导出。没有新建第二环境或更换全局运行时。

边界：本地向量验证不等于DeepSeek E10；E10继续NOT_VERIFIED至WP09。真实资料仍NOT_MET至WP10/真实效果验收前。生产批量吞吐、GPU优化、BGE-M3比较和跨语言真实真值为非阻断后续评估，不影响本包已测限定能力。
