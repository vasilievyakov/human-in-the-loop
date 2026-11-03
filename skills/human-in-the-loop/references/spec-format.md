# spec.json

```json
{
  "title": "SPEC.md: правки владельца",
  "intro": "Markdown под заголовком: что это и что нужно от владельца.",
  "task": "Инструкция агенту, попадает в выгрузку первой строкой.",
  "decisions": [{"value": "approve", "label": "Утверждаю как есть"}],
  "general_comment": true,
  "numbered": false,
  "file_stem": "spec-review",
  "item_defaults": {"status": false, "editable": false, "comment": true, "collapse": false},
  "items": [ ... ]
}
```

Все поля, кроме `items`, необязательны. `numbered` показывает номер у каждого блока. `file_stem` задает имя скачиваемых файлов. `item_defaults` задает флаги блоков, которые не указаны в самом блоке.

## Блок

```json
{
  "id": "s4",
  "heading": "С1. Политика источников",
  "level": 3,
  "meta": "Hacker News: Mistral",
  "link": "https://...",
  "body": "Markdown: заголовки, списки, таблицы, **жирный**, `код`.",
  "editable": true,
  "status": true,
  "comment": true,
  "collapse": false,
  "questions": [ ... ]
}
```

- `editable` — кнопка «Править текст»: исходный Markdown блока в редакторе, «Вернуть исходный». В выгрузке `markdown_old` и `markdown_new`, на странице появляется «Скачать Markdown».
- `status` — кнопки «Согласен» / «Нужна правка» / «Вопрос» (`ok` / `edit` / `ask`).
- `collapse` — длинный текст свернут до нескольких строк.
- `level` 3 рисует блок с отступом под блоком уровня 2.

## Вопросы

| type | Ответ в `answers` | Поля |
|---|---|---|
| `yesno` | `true` / `false` | `yes`, `no` — подписи кнопок |
| `choice` | `value` выбранного варианта | `options`: строки или `{"value", "label"}`; `free: true` — поле для своего ответа, текст идет в `notes` |
| `multi` | список `value` | `options`, `free` |
| `scale` | число от `start` (по умолчанию 1) | `levels`: подписи уровней по порядку; `colors: true` — от красного к зеленому |
| `text` | строка | `placeholder` |

Общие поля: `id` (уникален в блоке; для разметки одинаковый во всех блоках), `label`, `help` (Markdown мелким шрифтом), `required` (по умолчанию да, кроме `text`), `show_if: {"question": "ai", "equals": true}` — вопрос виден, только если ответ на более ранний вопрос этого блока равен значению. Скрытые вопросы не выгружаются и не считаются в прогрессе.

Блок считается готовым, когда отвечены все видимые обязательные вопросы; блок без вопросов — когда есть статус, комментарий или правка текста.

## Выгрузка

```json
{
  "task": "...", "title": "...", "spec_hash": "3233acfe20", "exported_at": "2026-11-02T13:12:43Z",
  "decision": "approve_with_changes", "general_comment": "",
  "items": [
    {"id": "s4", "heading": "С1...", "status": "edit", "comment": "...",
     "markdown_old": "...", "markdown_new": "...",
     "answers": {"q1": "вариант"}, "notes": {"q1": "свой ответ"}}
  ]
}
```

В `items` только тронутые блоки и только непустые поля.

## Слепая разметка

`sidecar.json` лежит рядом и на страницу не попадает:

```json
{"answers": {"<id блока>": {"<id вопроса>": "значение того же типа, что ответ владельца"}}}
```

`score.py labels.json sidecar.json --spec spec.json [--threshold 90]` печатает совпадение по каждому вопросу (для `scale` еще с точностью до одного деления) и все расхождения. Код выхода 1, если какой-то вопрос ниже порога. С `--spec` пара считается, только если вопрос виден по `show_if` у обеих сторон.
