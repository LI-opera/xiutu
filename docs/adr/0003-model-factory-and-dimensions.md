# ADR0003：显式模型factory及多维索引

日期2026-09-19；WP09用户授权扩展。现有固定E5索引384维不能容纳用户指定的本机BGE-M3 1024维。采用LLM/Embedding分别的协议+工厂，索引保存完整固定指纹，查询路由按索引配置，不按当前默认模型偷换。只允许受支持的384/1024维，数据库触发器检查每行维度；旧冻结索引可读，新索引按既有租约/资格事务原子激活。

本机已有官方ONNX及外置权重，不增加torch/FlagEmbedding依赖或下载。固定revision5617a9f61b028005a4858fdac845db406aefb181，文件hash保存在config与证据。BGE采用无前缀CLS+L2，480内容token窗口加权聚合；这是本项目预处理，不声称原8192token长上下文或稀疏/ColBERT功能全部验证。中文两个合成短句与查询真实编码：加载3.861s，两文档0.0972s，查询0.0370s，工作集1476MiB、峰值1488MiB（进程整体，单次温热短输入，不是压测）。首版Windows HANDLE采集失效记0，v2检查系统调用成功后才采用，原证据保留。

E5保持旧配置及模型文件，以双模型驻留换取冻结依据兼容；后续性能优化为待办。本包没有重做留出集、没有BGE质量优于E5的结论。新Linux BGE挂载示例未动态重验，仅Windows native MCP已实测。

官方依据：[BGE-M3模型卡/MIT](https://huggingface.co/BAAI/bge-m3)、[固定ONNX版本](https://huggingface.co/BAAI/bge-m3/tree/5617a9f61b028005a4858fdac845db406aefb181/onnx)。本机2.27GB文件逐一SHA256验证，无共享缓存写入。

DeepSeek使用锁定langchain-deepseek1.1.0，用户批准flash替换本轮旧chat，仅探针显式覆盖不改私有.env。SDK原生调用ID/JSON模式与执行器分层，未知模型/目标/配置不fallback。当前官方[价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)按峰时输入2元/百万、输出8元/百万保守预留，账本跨进程持久、失败不退款，所有窗口共用用户5元上限；不是每轮重新5元。
