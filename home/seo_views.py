"""
SEO marketing and campus landing page views.
"""

import json

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from .campus_config import (
    get_campus_by_seo_slug,
    get_campus_seo_slug,
    get_campuses_by_org,
    get_org_by_seo_slug,
    get_org_groups,
)
from .models import Confession, Event, RoomListing
from . import seo_config


def _base_context(request, breadcrumbs, faq_page_key=None, extra_schema=None):
    faqs = seo_config.get_faq_for_page(faq_page_key)
    graph = [
        seo_config.faq_schema_json(faqs),
        seo_config.breadcrumb_schema_json(breadcrumbs),
    ]
    if extra_schema:
        graph.append(extra_schema)
    schema = {"@context": "https://schema.org", "@graph": graph}
    return {
        "faqs": faqs,
        "breadcrumbs": breadcrumbs,
        "schema_json": json.dumps(schema, ensure_ascii=False),
        "canonical_url": request.build_absolute_uri(request.path),
    }


def _feature_page_context(request, page_key):
    page = seo_config.FEATURE_PAGES[page_key]
    breadcrumbs = [
        {"name": "Home", "url": seo_config.BASE_URL + "/"},
        {"name": page["h1"], "url": seo_config.BASE_URL + page["url_path"]},
    ]
    ctx = _base_context(request, breadcrumbs, faq_page_key=page.get("page_key"))
    ctx.update({
        "page": page,
        "internal_links": seo_config.INTERNAL_LINKS.get(page_key, []),
        "org_groups": get_org_groups(),
    })
    return ctx


def seo_campuses_view(request):
    ctx = _feature_page_context(request, "campuses")
    return render(request, "seo/feature_page.html", ctx)


def seo_student_matching_view(request):
    ctx = _feature_page_context(request, "student_matching")
    return render(request, "seo/feature_page.html", ctx)


def seo_roommate_finder_view(request):
    ctx = _feature_page_context(request, "college_roommate_finder")
    return render(request, "seo/feature_page.html", ctx)


def seo_confessions_view(request):
    ctx = _feature_page_context(request, "anonymous_campus_confessions")
    return render(request, "seo/feature_page.html", ctx)


def seo_campus_events_view(request):
    ctx = _feature_page_context(request, "campus_events")
    return render(request, "seo/feature_page.html", ctx)


def seo_campus_view(request, slug):
    """Handle /campus/<slug>/ for org pages (srm, vit, amrita) and campus pages (srm-ktr, etc.)."""
    org_name = get_org_by_seo_slug(slug)
    if org_name:
        return _org_landing_view(request, org_name, slug)

    campus = get_campus_by_seo_slug(slug)
    if campus:
        return _campus_landing_view(request, campus, slug)

    raise Http404()


def _org_landing_view(request, org_name, slug):
    content = seo_config.ORG_PAGE_CONTENT[org_name]
    org_slug = slug.lower()
    campuses = [{**c, "seo_slug": get_campus_seo_slug(c)} for c in get_campuses_by_org(org_name)]
    breadcrumbs = [
        {"name": "Home", "url": seo_config.BASE_URL + "/"},
        {"name": "Campuses", "url": seo_config.BASE_URL + reverse("seo_campuses")},
        {"name": org_name, "url": seo_config.BASE_URL + reverse("seo_campus", kwargs={"slug": org_slug})},
    ]
    web_page_schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": content["h1"],
        "description": content["meta_description"],
        "url": seo_config.BASE_URL + reverse("seo_campus", kwargs={"slug": org_slug}),
        "isPartOf": {"@type": "WebSite", "name": "KnotSpot", "url": seo_config.BASE_URL + "/"},
    }
    ctx = _base_context(request, breadcrumbs, extra_schema=web_page_schema)
    ctx.update({
        "content": content,
        "org_name": org_name,
        "org_slug": org_slug,
        "campuses": campuses,
        "page_type": "org",
    })
    return render(request, "seo/org_landing.html", ctx)


def _campus_landing_view(request, campus, slug):
    org_slug = campus["org"].lower()
    breadcrumbs = [
        {"name": "Home", "url": seo_config.BASE_URL + "/"},
        {"name": "Campuses", "url": seo_config.BASE_URL + reverse("seo_campuses")},
        {"name": campus["org"], "url": seo_config.BASE_URL + reverse("seo_campus", kwargs={"slug": org_slug})},
        {"name": campus["name"], "url": seo_config.BASE_URL + reverse("seo_campus", kwargs={"slug": slug})},
    ]
    campus_name = campus["name"]
    from django.db.models import Q
    campus_q = Q(campus=campus_name) | Q(campus__icontains=campus["code"])
    recent_confessions = Confession.objects.filter(
        campus_q, moderation_status="approved",
    ).order_by("-created_at")[:5]
    recent_events = Event.objects.filter(
        campus_q, status="approved",
    ).order_by("-created_at")[:5]
    recent_rooms = RoomListing.objects.filter(
        campus_q, is_active=True,
    ).order_by("-created_at")[:5]

    web_page_schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": f"{campus['name']} Student Community | KnotSpot",
        "description": (
            f"Find friends, roommates, confessions, and events at {campus['college']} "
            f"({campus['name']}) on KnotSpot."
        ),
        "url": seo_config.BASE_URL + reverse("seo_campus", kwargs={"slug": slug}),
    }
    ctx = _base_context(request, breadcrumbs, extra_schema=web_page_schema)
    ctx.update({
        "campus": campus,
        "campus_slug": slug,
        "org_slug": org_slug,
        "recent_confessions": recent_confessions,
        "recent_events": recent_events,
        "recent_rooms": recent_rooms,
        "sibling_campuses": [
            {**c, "seo_slug": get_campus_seo_slug(c)}
            for c in get_campuses_by_org(campus["org"])
        ],
        "page_type": "campus",
    })
    return render(request, "seo/campus_landing.html", ctx)


def founder_view(request):
    content = seo_config.FOUNDER_PAGE
    breadcrumbs = [
        {"name": "Home", "url": seo_config.BASE_URL + "/"},
        {"name": "About", "url": seo_config.BASE_URL + reverse("about")},
        {"name": "Arun Mohan K", "url": seo_config.BASE_URL + reverse("founder")},
    ]
    person_schema = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Arun Mohan K",
        "jobTitle": "Founder & Developer",
        "worksFor": {"@type": "Organization", "name": "KnotSpot", "url": seo_config.BASE_URL + "/"},
        "alumniOf": {
            "@type": "CollegeOrUniversity",
            "name": "SRM Institute of Science and Technology, Ramapuram Campus",
        },
        "homeLocation": {"@type": "Place", "name": "Malappuram, Kerala, India"},
        "sameAs": [content["instagram"]],
        "description": content["meta_description"],
    }
    ctx = _base_context(request, breadcrumbs, extra_schema=person_schema)
    ctx.update({"content": content})
    return render(request, "seo/founder.html", ctx)


def get_seo_sitemap_urls():
    """Return org and campus landing page URLs for sitemap (feature pages listed separately)."""
    pages = []
    for org_slug in ("srm", "vit", "amrita"):
        pages.append({
            "loc": f"/campus/{org_slug}/",
            "changefreq": "monthly",
            "priority": "0.8",
        })
    from .campus_config import CAMPUS_SEO_SLUGS
    for seo_slug in CAMPUS_SEO_SLUGS.values():
        pages.append({
            "loc": f"/campus/{seo_slug}/",
            "changefreq": "monthly",
            "priority": "0.7",
        })
    return pages
