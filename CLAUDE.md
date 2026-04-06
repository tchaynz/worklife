# WorkLife — Personal Multi-Agent Intelligence System

## What This Is

WorkLife is a personal AI Chief of Staff that runs 24/7 and communicates with you via WhatsApp. It uses specialist agents orchestrated by a Chief of Staff agent to handle different domains of your life — finance, logistics, research, travel, and more.

This is Milestone 1: **Life Side Chief of Staff** — personal use only, single user (Ted), no auth/billing/onboarding.

## Architecture

```
You (WhatsApp)
  ↕
WhatsApp Gateway (Twilio webhook → FastAPI)
  ↕
Chief of Staff Agent (orchestrator)
  ↕ routes to appropriate specialist
┌─────────────┬──────────────┬──────────────┬──────────────┐
│ Finance     │ Logistics    │ Research     │ Travel       │
│ Analyst     │ Manager      │ Scout        │ Planner      │
└─────────────┴──────────────┴──────────────┴──────────────┘
  ↕                ↕              ↕              ↕
Supabase (pgvector) — shared memory layer
```

## Tech Stack

- **Language**: Python 3.12+
- **Framework**: FastAPI
- **Database**: Supabase (PostgreSQL + pgvector extension)
- **LLM**: Anthropic Claude API (claude-sonnet-4-20250514)
- **Messaging**: Twilio WhatsApp Business API
- **Hosting**: Railway
- **Package manager**: uv (preferred) or pip

## Project Structure

```
worklife/
├── CLAUDE.md                  # This file — Claude Code reads this first
├── pyproject.toml             # Project config and dependencies
├── .env.example               # Required environment variables
├── README.md                  # Project overview
│
├── src/
│   ├── __init__.py
│   ├── main.py                # FastAPI app entry point
│   ├── config.py              # Settings, env vars, constants
│   │
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── whatsapp.py        # Twilio webhook handler (receive/send)
│   │   └── message_parser.py  # Parse incoming WhatsApp messages
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseAgent class (shared interface)
│   │   ├── chief_of_staff.py  # Orchestrator — routes to specialists
│   │   ├── finance.py         # Finance Analyst specialist
│   │   ├── logistics.py       # Logistics Manager specialist
│   │   ├── research.py        # Research Scout specialist
│   │   └── travel.py          # Travel Planner specialist
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── store.py           # Supabase read/write operations
│   │   ├── embeddings.py      # Generate embeddings for pgvector
│   │   └── context.py         # Build context window from memory
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── crypto.py          # CoinGecko API — price checks
│   │   ├── stocks.py          # Alpha Vantage API — stock data
│   │   ├── calendar.py        # Google Calendar API
│   │   ├── web_search.py      # Web search (Brave or Tavily API)
│   │   └── scraper.py         # Browserbase + Stagehand (future)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── anthropic_client.py # Claude API wrapper
│       └── logger.py          # Structured logging
│
├── db/
│   ├── schema.sql             # Supabase table definitions
│   └── migrations/            # Schema migrations
│
├── tests/
│   ├── __init__.py
│   ├── test_chief_of_staff.py
│   ├── test_agents.py
│   └── test_memory.py
│
├── scripts/
│   ├── seed_memory.py         # Seed initial context about Ted
│   └── test_whatsapp.py       # Local webhook testing
│
├── Procfile                   # Railway deployment
├── railway.toml               # Railway config
└── Dockerfile                 # Container config
```

## Environment Variables

```
# Anthropic
ANTHROPIC_API_KEY=

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_KEY=

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=
MY_WHATSAPP_NUMBER=

# Market Data
COINGECKO_API_KEY=
ALPHA_VANTAGE_API_KEY=

# Google (Milestone 2)
# GOOGLE_CREDENTIALS_JSON=

# App
APP_ENV=development
LOG_LEVEL=INFO
```

## Milestone 1 Phases

### Phase 1: Foundation (Week 1)
Build the skeleton — FastAPI app, Supabase connection, WhatsApp webhook, basic message round-trip.

**Tasks:**
1. Initialize project with uv, pyproject.toml, project structure
2. Set up FastAPI app with health check endpoint
3. Create Supabase project, run schema.sql (conversations, messages, agent_memory tables)
4. Implement Twilio WhatsApp webhook — receive message, echo it back
5. Implement Anthropic client wrapper with retry logic
6. Test end-to-end: send WhatsApp message → receive echo response via Claude

**Done when:** You can send a WhatsApp message and get a Claude-generated response back.

### Phase 2: Agent Framework (Week 2)
Build the multi-agent routing system.

**Tasks:**
1. Create BaseAgent class with standard interface: `async def process(message, context) -> AgentResponse`
2. Build Chief of Staff agent — uses Claude to classify intent and route to specialist
3. Implement agent registry — CoS looks up available specialists
4. Build conversation memory — store messages in Supabase, retrieve recent context
5. Implement context builder — pull relevant memory + conversation history into prompt
6. Create a stub specialist (Finance Analyst) that responds to finance queries
7. Test routing: send "what's the price of XRP?" → CoS routes to Finance → response

**Done when:** Messages route correctly to specialists based on intent, with conversation memory persisting across messages.

### Phase 3: Finance Analyst (Week 3)
First real specialist agent with live data.

**Tasks:**
1. Integrate CoinGecko API — fetch prices for XRP, XLM, FET, LINK, SOL
2. Integrate Alpha Vantage API — fetch SMCI stock price and basic fundamentals
3. Build Finance Analyst agent with system prompt:
   - Knows Ted's positions and hold-until-peak strategy
   - Can check current prices on demand
   - Can provide portfolio summary
   - Surfaces significant moves (>5% daily change)
4. Add portfolio context to agent memory (positions, entry points if known)
5. Test: "How are my positions doing?" → structured portfolio summary

**Done when:** You can ask about your crypto/stock positions via WhatsApp and get live data back.

### Phase 4: Logistics Manager (Week 3-4)
Calendar and schedule awareness.

**Tasks:**
1. Set up Google Cloud project with Calendar API enabled
2. Implement OAuth2 flow for Google account (one-time setup, store refresh token)
3. Build Logistics Manager agent:
   - Read upcoming events from Google Calendar
   - Summarize today's/this week's schedule
   - Awareness of kids' schedules (seeded into memory)
   - Surface conflicts or gaps
4. Test: "What's my week look like?" → calendar summary

**Done when:** You can ask about your schedule via WhatsApp and get calendar-aware responses.

### Phase 5: Research Scout + Travel Planner (Week 4-5)
Remaining specialist agents.

**Tasks:**
1. Integrate web search tool (Brave Search API or Tavily — both have free tiers)
2. Build Research Scout agent:
   - Deep research on topics you ask about
   - Can summarize findings from multiple sources
   - Stores research results in memory for future reference
3. Build Travel Planner agent:
   - Knows family preferences (seeded into memory)
   - Can research destinations, flights, accommodation
   - Integrates with calendar for availability awareness
4. Test both via WhatsApp

**Done when:** All four specialists respond accurately to domain-specific queries.

### Phase 6: Scheduled Tasks + Proactive Alerts (Week 5-6)
Make it always-on, not just reactive.

**Tasks:**
1. Add APScheduler or Railway cron jobs for recurring tasks
2. Finance Analyst: daily portfolio check at 9am ET, alert on >5% moves
3. Logistics Manager: morning briefing at 7am ET with today's schedule
4. Research Scout: weekly digest of topics you've flagged
5. Implement outbound WhatsApp messaging (agent-initiated, not just replies)
6. Add rate limiting and error handling for all external APIs

**Done when:** You wake up to a WhatsApp message from WorkLife with your morning briefing without having asked for it.

### Phase 7: Deploy + Harden (Week 6)
Production-ready on Railway.

**Tasks:**
1. Create Dockerfile and Procfile for Railway
2. Set all environment variables in Railway dashboard
3. Configure Twilio webhook to point to Railway URL
4. Add structured logging (JSON format for Railway logs)
5. Add error alerting — if an agent fails, you get notified
6. Test full system running on Railway for 48 hours
7. Monitor costs across all APIs

**Done when:** WorkLife runs on Railway 24/7 without intervention. You interact purely via WhatsApp.

## Coding Standards

- Type hints on all functions
- Async everywhere (FastAPI + httpx for external calls)
- Pydantic models for all data structures
- Each agent has its own system prompt in a constant at the top of its file
- No hardcoded secrets — everything from env vars
- Structured logging with context (agent name, message ID, latency)
- Tests for agent routing logic and memory operations

## Agent System Prompt Pattern

Every specialist agent follows this structure in its system prompt:

```
You are the [Role Name] for Ted's WorkLife system.

## Your Domain
[What you handle]

## What You Know About Ted
[Seeded context — positions, preferences, family details]

## Your Tools
[What APIs/data sources you can call]

## How You Respond
- Be concise — this goes to WhatsApp, not a document
- Lead with the answer, then context
- Use plain language, no markdown formatting
- If you need more info, ask one clear question
- If this isn't your domain, say so and the Chief of Staff will reroute
```

## Important Context for Claude Code

- This is a personal tool for a single user (Ted), not a multi-tenant SaaS
- WhatsApp messages are short — responses should be concise (under 300 words)
- The Chief of Staff agent is the ONLY agent that talks to the user — specialists return their response to the CoS who may synthesize or pass through
- Memory is persistent across conversations — agents should reference past context when relevant
- All external API calls should have graceful fallbacks if the service is down
- Railway has a 500MB memory limit on the hobby plan — keep the app lightweight
