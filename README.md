# 生日提醒助手

一个从 Obsidian 生日能力中拆出来的独立 AstrBot 插件。

## 功能

- 独立管理生日列表，不依赖 Obsidian 仓库
- 支持自然语言添加生日
- 支持自然语言删除生日
- 支持手动命令添加、删除、查看生日列表
- 支持 Pages 页面管理生日列表
- 支持自定义重复提醒日期，默认 `7 天 / 1 天 / 当天`
- 支持自定义提醒时间，默认 `08:00`
- 支持阳历、阴历、农历生日
- 支持农历生日自动换算下一次公历日期
- 生日过后第二天自动刷新为明年的公历生日
- 列表按 `1 月 -> 12 月` 排序展示
- 阴历/农历生日会在名字后显示 `（阴）` / `（农）`

## 指令

- `/birthday list` 查看全部生日列表
- `/birthday upcoming` 查看未来 30 天内的生日
- `/birthday show 名字` 查看某人的生日
- `/birthday add 雨林；生日：10月22日；历法：阳历；别名：小雨；备注：朋友`
- `/birthday add 天涯；生日：农历八月十五；历法：农历`
- `/birthday delete 雨林`
- `/birthday refresh` 立即刷新下一次公历生日映射
- `/birthday remind-now` 立即检查并推送今天应发送的生日提醒

## 自然语言示例

- `帮我添加雨林的生日是 10月22日`
- `把天涯的生日记到生日列表，生日是农历八月十五`
- `删除雨林的生日`
- `把天涯从生日列表删掉`
- `看看生日列表`
- `天涯的生日是几月几日`

## 数据存储

插件数据会保存在：

- `data/plugin_data/astrbot_plugin_birthday_reminder/birthdays.json`
- `data/plugin_data/astrbot_plugin_birthday_reminder/runtime_state.json`

## GitHub 仓库名建议

- `astrbot_plugin_birthday_reminder`

## 本地打包

在插件目录执行：

```bash
python build_portable_zip.py
```

会生成类似下面的安装包：

- `astrbot_plugin_birthday_reminder_0.1.0_server_flat_portable.zip`
