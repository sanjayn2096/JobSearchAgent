from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Contact:
    name: str
    title: str
    company: str
    email: str = ""
    linkedin_url: str = ""


@dataclass
class EmailDraft:
    contact: Contact
    job_id: str
    subject: str
    body: str
