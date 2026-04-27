pipeline {
  agent any

  options {
    timestamps()
  }

  environment {
    COMPOSE_FILE = "docker-compose.feiniu.yml"
    SERVICE_NAME = "fa860-bridge"
    HEALTH_URL = "http://127.0.0.1:9123/health"
  }

  stages {
    stage("Checkout") {
      steps {
        checkout scm
      }
    }

    stage("Validate Compose") {
      steps {
        sh "docker compose -f ${COMPOSE_FILE} config >/tmp/fa860-bridge-compose.yaml"
      }
    }

    stage("Deploy Bridge") {
      steps {
        sh "docker compose -f ${COMPOSE_FILE} up -d --build --force-recreate ${SERVICE_NAME}"
      }
    }

    stage("Health Check") {
      steps {
        sh '''
          set -eu
          for _ in $(seq 1 20); do
            if curl -fsS "$HEALTH_URL" >/tmp/fa860-bridge-health.json; then
              cat /tmp/fa860-bridge-health.json
              exit 0
            fi
            sleep 3
          done

          echo "FA860 bridge health check failed" >&2
          docker compose -f "$COMPOSE_FILE" logs --tail=100 "$SERVICE_NAME" || true
          exit 1
        '''
      }
    }
  }

  post {
    success {
      echo "FA860 bridge deployed successfully: ${HEALTH_URL}"
    }

    failure {
      sh 'docker compose -f "$COMPOSE_FILE" logs --tail=100 "$SERVICE_NAME" || true'
    }
  }
}