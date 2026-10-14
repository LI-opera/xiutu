# DKVB/P0299 专题接入契约

状态：IMPLEMENTED_NOT_ACCEPTED，限定资料检索与原页定位；不涉及诊断、规则注册或接受。

## 文件与接口
新增 backend/app/dkvb_preview.py（受信专题配置、范围检查和授权原页接口）、scripts/dkvb_topic.py（独立实例与幂等导入）、frontend/src/dkvb-topic.tsx（专题页）、相关定点测试。main.tsx仅选择专题页入口。无迁移，不修改旧服务的资格算法。

GET /api/v2/topic 返回服务端注册主题及就绪状态。POST /api/v2/topic/cases 用服务器车型创建冻结会话；POST /api/v2/topic/search 仅接受case_id/query/top_k。GET /api/v2/topic/cases/{case_id}/chunks/{chunk_id} 返回实际正文及来源映射。GET /api/v2/topic/sources/{source_id}/{page} 返回对应原PDF；/image 返回完整页图。所有入口需登录，写请求沿用Origin/CSRF。来源ID与页码仅在服务端封存白名单内解析，不接受本地路径。

## 导入与资格
先校验整个manifest的大小/SHA256。仅维修知识手册.md、规格与判断关系.md进入检索；保持synthetic=true及formal_usable=false。控制JSON、病例和说明不入库检索。三份PDF为非虚构待核实，仅原文查证，不审核/索引。两份正文经现有上传、worker解析、合成演示审核、BGE索引服务。部署登记只由本地可信导入器写入，浏览器不能授予范围。相同包/actor使用稳定幂等键、持久版本登记，重复导入不重建ready索引。

## 范围与原页
车型仅声明虚拟探岳、engine_code=DKVB；年款/发动机系列未知不补造。独立新库只有本包文档，专题会话还须验证manifest恰好对应白名单正文及有效BGE索引；不合格时失败，不默默扩大范围。查询使用冻结index及现有RetrievalService资格复验。源版本、chunk和正文hash先校验，再从实际正文/同段标题上下文提取S01—S03物理页引用。多页全部列出；找不到映射明确显示未提供。DS模拟标准显示独立警告及模拟规格正文，不把附近PDF当作阈值标准。页图只是原页展示，不代表向量理解图片。

## 部署及验证顺序
独立localhost端口、库、storage、构建与cookie；不覆盖5180。先manifest/映射/鉴权定点测试及独立构建，再真实PostgreSQL导入、BGE1024维索引、四问题检索、原页hash/重复导入检查，最后浏览器体验。模型离线，绝不加载付费配置。全部失败保留，仅复跑受影响项。

真实资料NOT_MET；PDF的来源/许可/精确适配仍未核实。未实施OCR、大文件、正式审核、观察写入、自动诊断及WP11—17。
