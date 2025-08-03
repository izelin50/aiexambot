import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def normalize_socials(socials):
    keys = {
        "vk.com/aitalenthub": "vkontakte",
        "ai.itmo.ru": "program_website",
        "t.me/aitalenthub": "telegram",
        "vk.com/abit.itmo": "abit_vk",
        "t.me/abit_itmo": "abit_telegram",
        "youtube.com": "youtube"
    }
    result = {v: None for v in keys.values()}
    for s in socials:
        url = s.get("url", "")
        for k, name in keys.items():
            if k in url:
                result[name] = url
    return result

def parse_itmo_program(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Используем видимый режим
        page = browser.new_page()
        try:
            print(f"Загружаем: {url}")
            page.goto(url, timeout=120000)

            # Ожидаем появления JSON
            json_str = None
            for i in range(30):
                json_str = page.evaluate("() => document.querySelector('#__NEXT_DATA__')?.innerText")
                if json_str:
                    break
                print(f"Ожидание JSON... ({i+1} сек)")
                time.sleep(1)

            if not json_str:
                raise Exception("JSON так и не появился на странице.")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            browser.close()
            return None

        browser.close()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ JSON-декодирование не удалось: {e}")
        return None

    return data  # Пока просто возвращаем весь __NEXT_DATA__

def main():
    parser = argparse.ArgumentParser(description="Парсер программ ИТМО")
    parser.add_argument('--url', required=True, help='Ссылка на программу, например: https://abit.itmo.ru/program/master/ai_product')
    parser.add_argument('--out', default='output.json', help='Путь к файлу для сохранения JSON')
    args = parser.parse_args()

    data = parse_itmo_program(args.url)
    if data:
        out_path = Path(args.out)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON сохранён в файл: {out_path.resolve()}")

if __name__ == "__main__":
    main()
