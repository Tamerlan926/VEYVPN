# 🚀 ВЕЙVPN Bot — Автоматизированный VPN сервис

Премиальный Telegram-бот для продажи и управления подписками VPN на базе протокола **VLESS + Reality**. Система включает в себя панель управления **3x-ui**, интеграцию с платежной системой **YooKassa** и современное **Mini App** внутри Telegram.

![Preview]([https://cdn-edge.kwork.ru/pics/t3/11/51576965-69f65aebd2429.jpg))

## ✨ Особенности

-   ⚡ **Мгновенная выдача ключей**: Автоматическое создание клиентов в панели 3x-ui.
-   💳 **Оплата через YooKassa**: Полностью автоматизированный процесс оплаты.
-   🎁 **Реферальная система**: +7 дней бесплатной подписки за каждого приглашенного друга.
-   📱 **Красивое Mini App**: Современный интерфейс для управления подпиской прямо в Telegram.
-    **Протокол VLESS + Reality**: Максимальная скорость и стабильность соединения.
-   🛡️ **Безопасность**: Секретные данные хранятся в `.env`, код открыт для аудита.

---

## 📋 Содержание

1.  [Покупка сервера](#1-покупка-сервера)
2.  [Установка панели 3x-ui](#2-установка-панели-3x-ui)
3.  [Настройка Inbound](#3-настройка-inbound)
4.  [Установка бота](#4-установка-бота)
5.  [Настройка конфигурации](#5-настройка-конфигурации)
6.  [Настройка Mini App](#6-настройка-mini-app)
7.  [Запуск бота](#7-запуск-бота)
8.  [Использование](#8-использование)
9.  [Благодарности](#9-благодарности)

---

## 1. Покупка сервера

Для работы бота необходим VPS (виртуальный сервер) с операционной системой **Ubuntu 20.04** или **22.04**.

### Рекомендуемый провайдер: [62yun.com](https://62yun.com)

1.  Перейдите на сайт [62yun.com](https://62yun.com).
2.  Выберите локацию: **Нидерланды (Netherlands)** или **Германия** для лучшей скорости.
3.  Выберите тариф: Минимум **2 CPU, 2 GB RAM, 20 GB SSD**.
4.  Оплатите сервер и получите данные для доступа (IP-адрес, логин `root`, пароль).

> 💡 **Совет:** Если вы новичок, рекомендую ознакомиться с подробным гайдом по настройке VPN от [ClusterM](https://github.com/ClusterM/vpn-how-to.git).

---

## 2. Установка панели 3x-ui

Панель **3x-ui** необходима для управления клиентами VPN. Мы используем популярный форк от [mhsanaei](https://github.com/mhsanaei/3x-ui).

1.  Подключитесь к серверу по SSH:
    ```bash
    ssh root@ВАШ_IP_АДРЕС
    ```

2.  Обновите систему:
    ```bash
    apt update && apt upgrade -y
    ```

3.  Установите панель одной командой:
    ```bash
    bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
    ```

4.  Следуйте инструкциям установщика:
    *   Введите порт панели (рекомендуется оставить по умолчанию или изменить на `80`).
    *   Введите логин и пароль для входа в панель (**запомните их!**).
    *   После установки панель будет доступна по адресу: `http://ВАШ_IP:ПОРТ`.

---

## 3. Настройка Inbound

1.  Войдите в панель 3x-ui, используя логин и пароль.
2.  Перейдите в раздел **Inbounds** → нажмите **Add Inbound**.
3.  Настройте параметры:
    *   **Protocol**: `VLESS`
    *   **Port**: `8443` (или любой другой свободный порт).
    *   **Stream Settings**:
        *   Network: `tcp`
        *   Security: `Reality`
        *   SNI: `aws.amazon.com` (или другой популярный сайт).
        *   Private Key: Сгенерируйте в панели или используйте готовый.
        *   Public Key: **Скопируйте его**, он понадобится для бота.
        *   Short ID: Сгенерируйте (например, `40`).
4.  Нажмите **Add**.
5.  **Запомните ID** этого инбаунда (цифра в колонке ID). Он понадобится для конфигурации бота.

---

## 4. Установка бота

1.  Установите необходимые пакеты:
    ```bash
    apt install python3 python3-pip git zip curl -y
    ```

2.  Клонируйте репозиторий:
    ```bash
    cd /root
    git clone https://github.com/ВАШ_НИК/VEYVPN.git ShadowVPNBot
    cd ShadowVPNBot
    ```

3.  Установите зависимости Python:
    ```bash
    pip3 install -r requirements.txt
    ```

---

## 5. Настройка конфигурации

1.  Создайте файл `.env` на основе примера:
    ```bash
    cp .env.example .env
    nano .env
    ```

2.  Заполните файл следующими данными:

    ```bash
    # Telegram Bot Token (получите у @BotFather)
    TG_BOT_TOKEN=123456:ABCDEF...

    # Server Settings
    SERVER_HOST=185.23.238.20 # Ваш IP адрес сервера
    TARGET_PORT=8443          # Порт из шага 3
    TARGET_INBOUND_ID=7       # ID инбаунда из панели 3x-ui

    # 3x-ui Panel Settings
    XUI_PANEL_URL=http://localhost:2053 # Адрес вашей панели (обычно localhost:2053 или localhost:80)
    XUI_PANEL_USER=admin                # Логин от панели
    XUI_PANEL_PASS=password             # Пароль от панели

    # Reality Settings
    REALITY_PUBKEY=ваш_public_key_из_панели
    REALITY_SHORT_IDS=40
    REALITY_SNI=aws.amazon.com
    REALITY_FP=chrome

    # YooKassa Payments (Optional)
    YOOKASSA_SHOP_ID=ваш_shop_id
    YOOKASSA_SECRET_KEY=ваш_secret_key

    # Support & Admins
    SUPPORT_USERNAME=@Ghost18274
    BOT_ADMINS=123456789 # Ваш Telegram ID
    ```

    > ⚠️ **Важно:** Никогда не публикуйте файл `.env` в открытом доступе!

---

## 6. Настройка Mini App

Mini App — это веб-интерфейс, который открывается внутри Telegram.

1.  Зарегистрируйтесь на [Netlify.com](https://netlify.com).
2.  Перетащите папку `ShadowVPNBot` (или только файл `app.html`) в область загрузки на сайте Netlify.
3.  Скопируйте полученную ссылку (например, `https://site-name.netlify.app`).
4.  Откройте файл `bot.py` и найдите строку:
    ```python
    k.button(text=" My Subscription", web_app=types.WebAppInfo(url="https://prismatic-cucurucho-d9e591.netlify.app/app.html"))
    ```
5.  Замените URL на вашу ссылку из Netlify.

---

## 7. Запуск бота

Для постоянной работы бота используем менеджер процессов **PM2**.

1.  Установите PM2:
    ```bash
    npm install pm2 -g
    ```

2.  Запустите бота:
    ```bash
    pm2 start bot.py --name "veyvpn-bot" --interpreter "/usr/bin/python3"
    ```

3.  Проверьте логи:
    ```bash
    pm2 logs veyvpn-bot
    ```
    Если вы видите `✅ Ready!`, значит бот успешно запущен.

4.  Сохраните автозапуск:
    ```bash
    pm2 save
    pm2 startup
    ```

---

## 8. Использование

1.  Найдите своего бота в Telegram по юзернейму.
2.  Напишите `/start`.
3.  Следуйте инструкциям меню:
    *   **Купить**: Выбор тарифа и оплата.
    *   **Моя подписка**: Открытие Mini App для управления подключением.
    *   **Ключи**: Просмотр текущего ключа.
    *   **Промокод**: Активация промокодов (например, `SHAKRIEV`, `KING`).

---

## 9. Благодарности

Этот проект создан с использованием следующих технологий и ресурсов:

*   [aiogram](https://docs.aiogram.dev/) — Фреймворк для Telegram ботов.
*   [3x-ui](https://github.com/mhsanaei/3x-ui) — Панель управления Xray/V2Ray.
*   [YooKassa](https://yookassa.ru/) — Платежная система.
*   [Netlify](https://netlify.com/) — Хостинг для Mini App.
*   [ClusterM vpn-how-to](https://github.com/ClusterM/vpn-how-to.git) — Гайд по настройке VPN.

---

## Лицензия

MIT License. См. файл [LICENSE](LICENSE) для деталей.

**Автор:** Tamerlan Shakriev  
**Версия:** 1.0.0
