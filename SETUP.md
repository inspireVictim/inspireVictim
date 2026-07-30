# Оформление профиля GitHub — как это работает и как залить

## Как это устроено

Никакого стороннего сервиса. Всё — обычные **SVG-файлы, лежащие в репозитории**,
которые генерирует `build.py` и раз в сутки пересобирает GitHub Action.

1. **Профильный README.** GitHub показывает на странице профиля README из репозитория,
   имя которого точно совпадает с логином. Для тебя это `inspireVictim/inspireVictim`.
2. **Картинки — свои SVG.** `build.py` рисует четыре карточки (`info-card`, `projects`,
   `stats`, `connect`) плюс по чипу на каждую ссылку. README подключает их через `<img>`.
3. **Тема.** Для каждой карточки собираются две версии — `-dark` и `-light`, а README
   переключает их через `<picture>` + `prefers-color-scheme`.
4. **Данные о контрибуциях** берутся с публичной страницы
   `github.com/users/<логин>/contributions` — токен не нужен.
5. **Кэш.** GitHub проксирует картинки через camo и кэширует их надолго, поэтому
   `build.py` дописывает к путям `?v=<метка времени>` при каждой сборке.

## Ограничения, из-за которых сделано именно так

- **Никакого JS внутри SVG** — GitHub его вырезает. Всё статично.
- **Никаких внешних шрифтов и картинок** внутри SVG — не загрузятся. Поэтому
  используется системный моноширинный стек, а иконки simple-icons вшиваются
  как `<path>` прямо в файл.
- **Ссылки внутри SVG не кликаются**, когда SVG вставлен как `<img>`. Поэтому
  строка контактов — это отдельные маленькие SVG-чипы, каждый обёрнут в `<a>` в README.

## Что нужно сделать тебе

### 1. Проверить и поправить `profile.json`

Я заполнил его по твоим репозиториям на GitHub и проектам из `~/projects`.
Проверь как минимум:

- `neofetch` — блок «о себе». **`Based: Bishkek, Kyrgyzstan` я предположил** по
  упоминанию КГТУ в репозитории `UniTeam` — поправь, если не так.
- `links` — сейчас только GitHub и почта `zzhaparovn@gmail.com`. Добавь портфолио,
  телеграм, LeetCode — что нужно. Поле `icon` — это slug с simple-icons.io.
- `projects` — 10 штук, приватные помечены `Private`. Названия/описания правь свободно.
- `handle` — что выводится в приглашении `<handle>@github ~ $`.

### 2. Создать репозиторий и залить

```bash
cd /Users/Crull/work/github-profile
git init -b main
git add -A
git commit -m "profile cards"
git remote add origin git@github.com:inspireVictim/inspireVictim.git
git push -u origin main
```

Репозиторий `inspireVictim/inspireVictim` должен быть создан заранее и быть **публичным**,
иначе README не покажется на профиле.

### 3. Разрешить Action писать в репозиторий

Settings → Actions → General → Workflow permissions → **Read and write permissions**.

После этого `.github/workflows/build.yml` будет каждый день в 03:17 UTC пересобирать
карточки и коммитить их. Запустить вручную — вкладка Actions → «build profile cards» → Run workflow.

## Локальная пересборка

```bash
pip3 install pillow
python3 build.py
```

Посмотреть результат локально:

```bash
python3 -m http.server 8777
# открыть http://localhost:8777/_preview.html
```

## Настройка ASCII-портрета

Блок `art` в `profile.json`:

| поле | что делает |
|---|---|
| `cols` | ширина в символах (больше — детальнее и крупнее) |
| `crop` | `[left, top, right, bottom]` — обрезка исходного фото в пикселях |
| `median` | сглаживание шума, радиус в пикселях |
| `cutoff` | процент отсечки при автоконтрасте |
| `contrast` | усиление контраста |
| `ramp` | `classic` (чисто), `detailed` (70 символов), `blocks` |
| `invert` | `true` для фото на **светлом** фоне — фон станет пустым |
| `cut` | яркость (0–255), выше которой пиксель считается фоном. Ниже — фон чище, но теряются детали лица |

Хочешь другое фото — положи его в `assets/avatar.jpg` и подбери `crop` и `cut`.

## Файлы

```
build.py                    генератор
profile.json                все данные
assets/avatar.jpg           исходное фото
assets/icons/               кэш иконок simple-icons
.github/workflows/build.yml ежедневная пересборка
README.md                   генерируется, руками не править
*-dark.svg / *-light.svg    генерируются, руками не править
```

Дополнительный текст под карточками можно добавить полем `readme_extra`
в `profile.json` — он допишется в конец README.
