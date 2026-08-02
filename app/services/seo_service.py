"""JSON-LD Schema.org structured data classes.

Mirrors the 17 Schema.org classes from AshaShop.Domain/Schema/,
including DecimalFormatConverter and ShortDateConverter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID


# ── Converters (mirrors DecimalFormatConverter.cs, ShortDateConverter.cs) ──

class DecimalFormatConverter:
    @staticmethod
    def format(value: Optional[float]) -> int:
        return int(round(value)) if value is not None else 0

    @staticmethod
    def format_nullable(value: Optional[float]) -> Optional[int]:
        return int(round(value)) if value is not None else None


class ShortDateConverter:
    @staticmethod
    def format(value: Optional[datetime]) -> Optional[str]:
        return value.strftime("%Y-%m-%d") if value is not None else None

    @staticmethod
    def format_required(value: Optional[datetime], default: str = "") -> str:
        return value.strftime("%Y-%m-%d") if value is not None else default


class AdditionalProperty:
    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value

    def to_dict(self) -> dict:
        return {
            "@type": "PropertyValue",
            "name": self.name,
            "value": self.value,
        }


class PostalAddress:
    def __init__(
        self,
        street_address: Optional[str] = None,
        address_locality: Optional[str] = None,
        address_region: Optional[str] = None,
        address_country: Optional[str] = "IR",
        postal_code: Optional[str] = None,
    ):
        self.street_address = street_address
        self.address_locality = address_locality
        self.address_region = address_region
        self.address_country = address_country
        self.postal_code = postal_code

    def to_dict(self) -> dict:
        d: dict = {"@type": "PostalAddress"}
        if self.street_address:
            d["streetAddress"] = self.street_address
        if self.address_locality:
            d["addressLocality"] = self.address_locality
        if self.address_region:
            d["addressRegion"] = self.address_region
        if self.address_country:
            d["addressCountry"] = self.address_country
        if self.postal_code:
            d["postalCode"] = self.postal_code
        return d


class ContactPoint:
    def __init__(self, telephone: Optional[str] = None, contact_type: Optional[str] = "customer service"):
        self.telephone = telephone
        self.contact_type = contact_type

    def to_dict(self) -> dict:
        d: dict = {"@type": "ContactPoint"}
        if self.telephone:
            d["telephone"] = self.telephone
        if self.contact_type:
            d["contactType"] = self.contact_type
        return d


class Rating:
    def __init__(self, rating_value: float, best_rating: int = 5, worst_rating: int = 1):
        self.rating_value = rating_value
        self.best_rating = best_rating
        self.worst_rating = worst_rating

    def to_dict(self) -> dict:
        return {
            "@type": "Rating",
            "ratingValue": self.rating_value,
            "bestRating": self.best_rating,
            "worstRating": self.worst_rating,
        }


class AggregateRating:
    def __init__(self, rating_value: float, review_count: int, best_rating: int = 5, worst_rating: int = 1):
        self.rating_value = rating_value
        self.review_count = review_count
        self.best_rating = best_rating
        self.worst_rating = worst_rating

    def to_dict(self) -> dict:
        return {
            "@type": "AggregateRating",
            "ratingValue": self.rating_value,
            "reviewCount": self.review_count,
            "bestRating": self.best_rating,
            "worstRating": self.worst_rating,
        }


class Brand:
    def __init__(self, name: str):
        self.name = name

    def to_dict(self) -> dict:
        return {"@type": "Brand", "name": self.name}


class Offer:
    def __init__(
        self,
        price: float,
        price_currency: str = "IRR",
        url: Optional[str] = None,
        availability: str = "https://schema.org/InStock",
        price_valid_until: Optional[datetime] = None,
    ):
        self.price = price
        self.price_currency = price_currency
        self.url = url
        self.availability = availability
        self.price_valid_until = price_valid_until

    def to_dict(self) -> dict:
        d: dict = {
            "@type": "Offer",
            "price": int(self.price),
            "priceCurrency": self.price_currency,
            "availability": self.availability,
        }
        if self.url:
            d["url"] = self.url
        if self.price_valid_until:
            d["priceValidUntil"] = self.price_valid_until.strftime("%Y-%m-%d")
        return d


class Person:
    def __init__(self, name: str):
        self.name = name

    def to_dict(self) -> dict:
        return {"@type": "Person", "name": self.name}


class Review:
    def __init__(
        self,
        author: Person,
        review_body: str,
        review_rating: Optional[Rating] = None,
        date_published: Optional[datetime] = None,
        publisher: Optional[Person] = None,
    ):
        self.author = author
        self.review_body = review_body
        self.review_rating = review_rating
        self.date_published = date_published
        self.publisher = publisher

    def to_dict(self) -> dict:
        d: dict = {
            "@type": "Review",
            "author": self.author.to_dict(),
            "reviewBody": self.review_body,
        }
        if self.review_rating:
            d["reviewRating"] = self.review_rating.to_dict()
        if self.date_published:
            d["datePublished"] = self.date_published.strftime("%Y-%m-%d")
        if self.publisher:
            d["publisher"] = self.publisher.to_dict()
        return d


class ProductSchema:
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        sku: Optional[str] = None,
        image: Optional[str] = None,
        url: Optional[str] = None,
        model: Optional[str] = None,
        brand: Optional[Brand] = None,
        category: Optional[str] = None,
        offers: Optional[Offer] = None,
        aggregate_rating: Optional[AggregateRating] = None,
        review: Optional[list[Review]] = None,
        additional_property: Optional[list[AdditionalProperty]] = None,
    ):
        self.name = name
        self.description = description
        self.sku = sku
        self.image = image
        self.url = url
        self.model = model
        self.brand = brand
        self.category = category
        self.offers = offers
        self.aggregate_rating = aggregate_rating
        self.review = review
        self.additional_property = additional_property

    def to_dict(self) -> dict:
        d: dict = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": self.name,
        }
        if self.description:
            d["description"] = self.description
        if self.sku:
            d["sku"] = self.sku
        if self.image:
            d["image"] = self.image
        if self.url:
            d["url"] = self.url
        if self.model:
            d["model"] = self.model
        if self.brand:
            d["brand"] = self.brand.to_dict()
        if self.category:
            d["category"] = self.category
        if self.offers:
            d["offers"] = self.offers.to_dict()
        if self.aggregate_rating:
            d["aggregateRating"] = self.aggregate_rating.to_dict()
        if self.review:
            d["review"] = [r.to_dict() for r in self.review]
        if self.additional_property:
            d["additionalProperty"] = [p.to_dict() for p in self.additional_property]
        return d


class OrganizationSchema:
    def __init__(
        self,
        name: str,
        url: Optional[str] = None,
        logo: Optional[str] = None,
        contact_point: Optional[ContactPoint] = None,
        same_as: Optional[list[str]] = None,
    ):
        self.name = name
        self.url = url
        self.logo = logo
        self.contact_point = contact_point
        self.same_as = same_as

    def to_dict(self) -> dict:
        d: dict = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": self.name,
        }
        if self.url:
            d["url"] = self.url
        if self.logo:
            d["logo"] = self.logo
        if self.contact_point:
            d["contactPoint"] = self.contact_point.to_dict()
        if self.same_as:
            d["sameAs"] = self.same_as
        return d


class WebsiteSchema:
    def __init__(
        self,
        name: str,
        url: str,
        search_action: Optional["SearchAction"] = None,
    ):
        self.name = name
        self.url = url
        self.search_action = search_action

    def to_dict(self) -> dict:
        d: dict = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": self.name,
            "url": self.url,
        }
        if self.search_action:
            d["potentialAction"] = self.search_action.to_dict()
        return d


class SearchAction:
    def __init__(self, target: str, query_input: str = "required name=search_term_string"):
        self.target = target
        self.query_input = query_input

    def to_dict(self) -> dict:
        return {
            "@type": "SearchAction",
            "target": self.target,
            "query-input": self.query_input,
        }


class StoreSchema:
    def __init__(
        self,
        name: str,
        address: Optional[PostalAddress] = None,
        telephone: Optional[str] = None,
        opening_hours: Optional[str] = None,
    ):
        self.name = name
        self.address = address
        self.telephone = telephone
        self.opening_hours = opening_hours

    def to_dict(self) -> dict:
        d: dict = {
            "@context": "https://schema.org",
            "@type": "Store",
            "name": self.name,
        }
        if self.address:
            d["address"] = self.address.to_dict()
        if self.telephone:
            d["telephone"] = self.telephone
        if self.opening_hours:
            d["openingHours"] = self.opening_hours
        return d


class CollectionPageSchema:
    def __init__(self, name: str, description: Optional[str] = None, url: Optional[str] = None):
        self.name = name
        self.description = description
        self.url = url

    def to_dict(self) -> dict:
        d: dict = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": self.name,
        }
        if self.description:
            d["description"] = self.description
        if self.url:
            d["url"] = self.url
        return d


class BreadcrumbSchema:
    def __init__(self, item_list_element: list[dict]):
        self.item_list_element = item_list_element

    def to_dict(self) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": self.item_list_element,
        }


def breadcrumb_item(position: int, name: str, item_url: str) -> dict:
    return {
        "@type": "ListItem",
        "position": position,
        "name": name,
        "item": item_url,
    }