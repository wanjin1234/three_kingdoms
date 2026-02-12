# 三国游戏开发说明文档

## 一、文件架构：

``` text
three_kingdoms/
├── .gitignore              <-- 【核心】git忽略文件
├── README.md               <-- 项目说明书
├── requirements.txt        <-- 依赖库列表
├── main.py                 <-- 【入口】游戏的启动文件
├── settings.py             <-- 【配置】全局变量（屏幕大小、FPS、颜色）
├── assets/                 <-- 【资源库】所有非代码的东西
│   ├── map/                <-- 钢铁雄心的灵魂：地图
│   │   ├── visual.png      <-- 给玩家看的高清地图
│   │   ├── provinces.bmp   <-- 给代码看的省份色块图
│   │   └── definitions.csv <-- 省份数据表（ID, 名字, 地形）
│   ├── graphics/           <-- 图片
│   │   ├── units/          <-- 兵牌/Sprite
│   │   ├── flags/          <-- 国旗
│   │   └── ui/             <-- 界面按钮、面板背景
│   ├── fonts/              <-- 字体
│   └── data/               <-- 游戏数值
│       ├── kingdoms.json   <-- 国家定义
│       └── units.json      <-- 兵种属性
└── src/                    <-- 【源代码】所有逻辑代码
    ├── __init__.py
    ├── core/               <-- 核心引擎
    │   ├── __init__.py
    │   ├── app.py          <-- 游戏主循环类
    │   ├── camera.py       <-- 摄像机控制
    │   └── events.py       <-- 输入事件处理
    ├── map/                <-- 地图系统
    │   ├── __init__.py
    │   ├── map_manager.py  <-- 地图加载与渲染
    │   └── province.py     <-- 省份类
    ├── game_objects/       <-- 游戏对象
    │   ├── __init__.py
    │   ├── unit.py         <-- 军队类
    │   └── kingdom.py      <-- 国家类
    └── ui/                 <-- 界面系统
        ├── __init__.py
        └── panels.py       <-- 信息面板
```

