# Docker Compose для HeadHunter Search

Этот проект настроен для запуска в Docker с использованием nginx в качестве reverse proxy.

## Структура

- **Backend**: FastAPI приложение на порту 8000
- **Nginx**: Reverse proxy на порту 81 (внешний)
- **База данных**: SQLite файл монтируется как volume

## Запуск

### 1. Сборка и запуск всех сервисов

```bash
docker-compose up --build
```

### 2. Запуск в фоновом режиме

```bash
docker-compose up -d --build
```

### 3. Остановка

```bash
docker-compose down
```

## Доступ к приложению

После запуска приложение будет доступно по адресу:
- **http://localhost:81**

## Логи

### Просмотр логов всех сервисов
```bash
docker-compose logs
```

### Просмотр логов конкретного сервиса
```bash
docker-compose logs backend
docker-compose logs nginx
```

### Просмотр логов в реальном времени
```bash
docker-compose logs -f
```

## Пересборка

При изменении кода приложения:

```bash
docker-compose up --build
```

## Переменные окружения

Все переменные окружения настраиваются в файле `docker-compose.yml` в секции `environment` для backend сервиса.

## База данных

База данных SQLite монтируется как volume, поэтому данные сохраняются между перезапусками контейнеров.

## Troubleshooting

### Проверка статуса контейнеров
```bash
docker-compose ps
```

### Вход в контейнер backend
```bash
docker-compose exec backend bash
```

### Вход в контейнер nginx
```bash
docker-compose exec nginx sh
```

### Очистка всех данных
```bash
docker-compose down -v
docker system prune -a
``` 