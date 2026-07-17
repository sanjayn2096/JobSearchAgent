from __future__ import annotations

import logging

import aiohttp

from app.domain.entities.outreach import Contact

logger = logging.getLogger(__name__)

_APOLLO_URL = "https://api.apollo.io/api/v1/mixed_people/search"
_RECRUITER_TITLES = ["Recruiter", "Technical Recruiter", "Talent Acquisition", "Recruiting Manager"]
_HIRING_MGR_TITLES = ["Engineering Manager", "Hiring Manager", "VP of Engineering", "Director of Engineering"]


class ApolloSource:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def find(self, company: str) -> list[Contact]:
        async with aiohttp.ClientSession() as session:
            recruiter = await self._search(session, company, _RECRUITER_TITLES, limit=1)
            hiring_mgr = await self._search(session, company, _HIRING_MGR_TITLES, limit=1)
        return (recruiter + hiring_mgr)[:2]

    async def _search(
        self, session: aiohttp.ClientSession, company: str, titles: list[str], limit: int
    ) -> list[Contact]:
        payload = {
            "api_key": self._api_key,
            "q_organization_name": company,
            "person_titles": titles,
            "page": 1,
            "per_page": limit,
        }
        try:
            async with session.post(
                _APOLLO_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning("Apollo %s for %s", resp.status, company)
                    return []
                data = await resp.json()
        except Exception as exc:
            logger.warning("Apollo failed for %s: %s", company, exc)
            return []

        contacts = []
        for person in data.get("people", []):
            email = person.get("email") or person.get("contact", {}).get("email", "")
            contacts.append(
                Contact(
                    name=person.get("name", ""),
                    title=person.get("title", ""),
                    company=company,
                    email=email,
                    linkedin_url=person.get("linkedin_url", ""),
                )
            )
        return contacts
