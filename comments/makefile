PRODUCTION_PORT=80
DEVELOPMENT_PORT=8080

HOST_SUBMISSIONS_ROOT=/path/to/submissions
CONTAINER_SUBMISSIONS_ROOT=/student

LLM_MODEL=phi4-mini:3.8b

dev-serve: build
	@echo "Starting comments_service_dev container (press Ctrl-C to stop)..."
	@docker run --rm -d --name comments_service_dev -p 8080:80 \
		-v "${HOST_SUBMISSIONS_ROOT}":${CONTAINER_SUBMISSIONS_ROOT} \
		-v ollama_data:/root/.ollama \
		-e SUBMISSIONS_ROOT=${CONTAINER_SUBMISSIONS_ROOT} \
		-e LLM_MODEL=${LLM_MODEL} \
		-e BRANCH=Development \
		comments
	@bash -c 'trap "echo Received SIGINT; $(MAKE) dev-kill; exit 0" INT; while true; do sleep 1; done'

serve:
	docker run --rm -d --name comments_service -p 80:80 \
		-v "${HOST_SUBMISSIONS_ROOT}":${CONTAINER_SUBMISSIONS_ROOT} \
		-v ollama_data:/root/.ollama \
		-e SUBMISSIONS_ROOT=${CONTAINER_SUBMISSIONS_ROOT} \
		-e LLM_MODEL=${LLM_MODEL} \
		-e BRANCH=Production \
		comments

dev-kill:
	-docker kill comments_service_dev || true

kill:
	-docker kill comments_service || true

build:
	docker build -t comments .
