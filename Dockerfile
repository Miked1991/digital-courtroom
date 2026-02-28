# Build the image
docker build -t automaton-auditor .

# Run with volume mount for audit output
docker run -v $(pwd)/audits:/app/audits \
  -e GROQ_API_KEY=your_key_here \
  automaton-auditor \
  --repo https://github.com/username/repo \
  --pdf /app/report.pdf

# Or with env file
docker run --env-file .env \
  -v $(pwd)/audits:/app/audits \
  -v $(pwd)/reports:/app/reports \
  automaton-auditor \
  --repo https://github.com/username/repo \
  --pdf /app/reports/report.pdf