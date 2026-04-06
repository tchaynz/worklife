"""
Seed initial memory for WorkLife agents.
Run once after setting up Supabase to give agents baseline context about Ted.

Usage:
    uv run python -m scripts.seed_memory
"""
import asyncio
import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from src.memory.store import save_memory

SEED_MEMORIES = [
    # Finance Analyst context
    {
        "agent_name": "finance",
        "category": "fact",
        "content": "Ted holds the following crypto positions: XRP, XLM, FET, LINK, SOL. Strategy is hold-until-peak. No day trading.",
    },
    {
        "agent_name": "finance",
        "category": "fact",
        "content": "Ted holds SMCI (Super Micro Computer) stock. Strategy is hold-until-peak.",
    },
    {
        "agent_name": "finance",
        "category": "preference",
        "content": "Ted wants to be alerted on any position moving more than 5% in a single day. He does not want trade recommendations — only information and signals for his own decision-making.",
    },

    # Logistics Manager context
    {
        "agent_name": "logistics",
        "category": "fact",
        "content": "Ted lives in Montreal, Quebec, Canada with his wife Sue and their children.",
    },
    {
        "agent_name": "logistics",
        "category": "fact",
        "content": "Ted works as VP of Design at Workleap. Standard work hours are roughly 9am-6pm ET weekdays.",
    },
    {
        "agent_name": "logistics",
        "category": "preference",
        "content": "Ted wants a morning briefing at 7am ET with today's schedule, weather, and any alerts from other agents.",
    },

    # Research Scout context
    {
        "agent_name": "research",
        "category": "preference",
        "content": "Ted has broad intellectual interests including physics, classical literature, geopolitics, AI/ML, design systems, and B2B SaaS.",
    },
    {
        "agent_name": "research",
        "category": "fact",
        "content": "Ted is exploring side business opportunities. Key areas of expertise: B2B SaaS design leadership, Microsoft 365 ecosystem, AI-native tooling, design systems.",
    },

    # Travel Planner context
    {
        "agent_name": "travel",
        "category": "fact",
        "content": "Ted's family is based in Montreal. They are considering a potential overseas relocation — Portugal and Netherlands are current options under research.",
    },
    {
        "agent_name": "travel",
        "category": "preference",
        "content": "Ted's family travels need to work around school schedules for the kids. Vacation planning should account for this.",
    },
    {
        "agent_name": "travel",
        "category": "fact",
        "content": "Ted and Sue own property at Domaine Boréa which has an ongoing municipal legal situation with Miller Thomson handling it.",
    },

    # Chief of Staff context
    {
        "agent_name": "chief_of_staff",
        "category": "preference",
        "content": "Ted prefers concise, direct communication. No fluff. Lead with the answer. He wants to be challenged on his thinking, not agreed with.",
    },
    {
        "agent_name": "chief_of_staff",
        "category": "preference",
        "content": "Ted uses WhatsApp as his primary interaction channel with WorkLife. Keep responses under 300 words unless he asks for detail.",
    },
]


async def main() -> None:
    print(f"Seeding {len(SEED_MEMORIES)} memories into Supabase...")
    for i, mem in enumerate(SEED_MEMORIES, 1):
        await save_memory(
            agent_name=mem["agent_name"],
            category=mem["category"],
            content=mem["content"],
        )
        print(f"  [{i}/{len(SEED_MEMORIES)}] {mem['agent_name']} / {mem['category']}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
