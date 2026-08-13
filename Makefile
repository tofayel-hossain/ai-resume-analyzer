run:
	streamlit run app.py

test:
	pytest -q

docker:
	docker compose up --build
