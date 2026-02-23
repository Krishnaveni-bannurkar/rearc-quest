.PHONY: install poetry export-requirements deploy

# Install dependencies (local dev)
install:
	poetry install

# Alias: run Poetry install
poetry: install

# Export Poetry lock to requirements.txt for Databricks serverless (Poetry 2.x needs plugin)
export-requirements:
	poetry self add poetry-plugin-export 2>/dev/null || true
	poetry lock
	poetry export -f requirements.txt --without-hashes -o requirements.txt

# Deploy to Databricks (run from products/rearc). Use poetry env so brickflows 1.6+ is used (serverless).
deploy: export-requirements
	cd ../.. && poetry -C products/rearc run brickflow projects deploy --project rearc