# AnalogStepik

AnalogStepik - учебная платформа с курсами, задачами, отправкой решений и проверкой кода через backend API.

## Запуск

```bash
docker compose up --build
```

После запуска:

- backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- frontend: http://localhost:3000
- RabbitMQ UI: http://localhost:15672

## Frontend

Фронтенд лежит в `frontend/` и работает как статическая SPA без npm-зависимостей. Он покрывает текущие роуты:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /users/me`
- `GET /users/me/stats`
- `GET /users/{user_id}`
- `GET /courses/`
- `GET /courses/my`
- `GET /courses/my/created`
- `GET /courses/{course_id}`
- `POST /courses/`
- `PUT /courses/{course_id}`
- `DELETE /courses/{course_id}`
- `POST /courses/{course_id}/enroll`
- `POST /courses/{course_id}/unenroll`
- `GET /tasks/`
- `GET /tasks/{task_id}`
- `POST /tasks/`
- `POST /submissions/`
- `GET /submissions/{submission_id}`
