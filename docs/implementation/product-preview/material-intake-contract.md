# 上传提示及资料待审核入口契约

本次为已接受预览切片后续改进，IMPLEMENTED_NOT_ACCEPTED；不改变历史接受范围，不部署5180，不进入WP11。

文件：backend/app/product_preview.py、frontend/src/main.tsx、新增material-intake.ts及测试；复用DocumentInput、原上传/解析/版本/原文/chunks。无需迁移，不改Upload字节限额及formal/synthetic资格算法。配置GET /api/v2/preview/config返回upload_max_bytes（实际Settings值）。

普通上传必须明确选synthetic或nonfiction，无默认选择。合成上传沿用固定演示scope；非虚构上传synthetic=false，source_kind=unverified_material，source_reference由来源说明或明确“来源未知，待核实”填写；source_status和license_status均unknown。车型/年款范围/发动机可选，留空为null，绝不填虚构值。filename仅title。两类均未审核；专用虚构样例按钮保留明确标记的历史来源。

前端File.size与服务端max逐字节比较，等于上限可提交，超限禁用并显示中文大小提示；后端继续限制实际接收字节。后端413显示请求过限说明，不仅依赖前端。失败不changeContext，成功才切换/清空依赖状态。

非虚构资料只上传/解析/查看元数据、原文、切块及缺项；预览服务子类在review入口根据已授权不可变version.metadata.synthetic拒绝非虚构资料（403 PREVIEW_REVIEW_SYNTHETIC_ONLY），含直接HTTP请求与重放。原资格门禁继续排除非合成资料，不自动索引、创建正式case或规则。页面隐藏合成确认控件，不用绿色状态代替资格。元数据误填不自动修正历史；用户应重新上传并正确声明，不能把文件重新标记为verified。

测试：新库与独立storage；服务端边界1024字节测试配置仅缩小测试实例，不变更默认25MiB。覆盖1023/1024/1025实际文件字节、两类元数据、review拒绝及范围排除、失败/成功上下文；浏览器实际两类入口，合成用本地E5，非虚构测试载荷明确是流程夹具，不代表真实手册。前端读取配置、检查/构建独立输出，不覆盖5180。用户PDF路径、大小、文字层未核实，仍不支持超限整本/分片/OCR。
