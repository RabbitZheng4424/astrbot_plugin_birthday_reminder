# 生日提醒助手

一个从 Obsidian 生日能力中拆出来的独立 AstrBot 插件，用来单独管理生日列表、处理生日提醒，并支持自然语言增删生日信息。

## 插件说明

这个插件不依赖 Obsidian 仓库，适合直接在 AstrBot 中使用。你可以手动维护生日列表，也可以让机器人通过自然语言帮你添加、删除和查询生日。

除了普通阳历生日外，它也支持阴历、农历生日，并会自动计算下一次对应的公历日期。生日过后，插件会在第二天自动切换到下一年的公历生日映射，避免提醒停留在过期日期上。

## 功能特点

- 独立管理生日列表，不依赖 Obsidian
- 支持自然语言添加、删除、查询生日
- 支持手动命令添加、删除、查看生日列表
- 支持 Pages 页面管理生日数据
- 支持自定义提醒时间，默认 `08:00`
- 支持自定义重复提醒日期，默认 `生日前 7 天 / 前 1 天 / 当天`
- 支持阳历、阴历、农历生日
- 支持农历生日自动换算下一次公历日期
- 生日过后第二天自动刷新为下一年的公历日期
- 生日列表按 `1 月 -> 12 月` 排序显示
- 阴历 / 农历生日会在名字后自动显示 `（阴）` / `（农）`

## 指令用法

- `/birthday list` 查看全部生日列表
- `/birthday upcoming` 查看未来 30 天内的生日
- `/birthday show 名字` 查看某个人的生日信息
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

插件运行后的数据默认保存在下面两个文件中：

- `data/plugin_data/astrbot_plugin_birthday_reminder/birthdays.json`
- `data/plugin_data/astrbot_plugin_birthday_reminder/runtime_state.json`

## 本地打包

在插件目录执行：

```bash
python build_portable_zip.py
```

默认会生成类似下面的安装包：

- `astrbot_plugin_birthday_reminder_0.1.0_server_flat_portable.zip`
