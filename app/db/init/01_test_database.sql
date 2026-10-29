-- Base de pruebas, aparte de la de trabajo.
--
-- Los tests la truncan entre casos, así que compartir la base de desarrollo
-- significaría perder el almanaque local en cada `pytest`. La suite apunta a
-- `fellowship_test` (se puede cambiar con FELLOWSHIP_TEST_DATABASE_URL).

CREATE DATABASE fellowship_test OWNER fellowship;
