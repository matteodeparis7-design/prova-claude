"""Agente "Spesa intelligente": ricette con i prodotti in offerta e lista della spesa con il totale."""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from ...llm import LLM
from ...models import Offer
from ...money import format_eur


class AIIngredient(BaseModel):
    name: str = Field(description="Ingrediente, es. 'spaghetti'")
    quantity: str = Field(description="Quantità, es. '320 g'")
    offer_id: int | None = Field(description="id dell'offerta usata per questo ingrediente, o null")


class AIRecipe(BaseModel):
    title: str
    servings: int
    minutes: int = Field(description="Tempo totale in minuti")
    ingredients: list[AIIngredient]
    steps: list[str]


class AIRecipes(BaseModel):
    recipes: list[AIRecipe]


@dataclass
class ShoppingLine:
    offer_id: int
    name: str
    quantity: int
    unit_price_cents: int

    @property
    def total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


_SYSTEM = (
    "Sei l'agente Spesa intelligente di un supermercato italiano. Proponi ricette casalinghe, realistiche "
    "e sicure, che usino il più possibile i prodotti in offerta forniti. Per ogni ingrediente in offerta "
    "indica il suo offer_id esatto; per gli ingredienti comuni non in offerta (sale, acqua, spezie) usa null. "
    "Non inventare offerte né prezzi. Passaggi brevi e chiari, in italiano."
)


def suggest_recipes(llm: LLM, offers: list[Offer], request: str = "", count: int = 3,
                    servings: int = 4) -> list[dict]:
    if not offers:
        return []
    count = max(1, min(count, 5))
    servings = max(1, min(servings, 12))
    catalog = "\n".join(f"- offer_id={o.id}: {o.name} {o.description} ({format_eur(o.price_cents)}), "
                        f"categoria {o.category}" for o in offers[:80])
    prompt = (f"Prodotti in offerta:\n{catalog}\n\nRichiesta del cliente: {request.strip()[:500] or 'nessuna'}\n"
              f"Proponi {count} ricette per {servings} persone.")
    res = llm.parse(system=_SYSTEM, content=[{"type": "text", "text": prompt}], schema=AIRecipes,
                    effort="medium", max_tokens=12000)
    by_id = {o.id: o for o in offers}
    out = []
    for r in res.recipes[:count]:
        ingredients = []
        for ing in r.ingredients:
            o = by_id.get(ing.offer_id) if ing.offer_id is not None else None
            ingredients.append({
                "name": ing.name, "quantity": ing.quantity,
                # Un id inesistente viene scartato: mai un'offerta inventata.
                "offer_id": o.id if o else None,
                "offer": {"name": o.name, "price": format_eur(o.price_cents)} if o else None,
            })
        out.append({"title": r.title, "servings": r.servings, "minutes": max(1, r.minutes),
                    "ingredients": ingredients, "steps": [s for s in r.steps if s.strip()]})
    return out


def shopping_list(offers: list[Offer], wanted: dict[int, int]) -> tuple[list[ShoppingLine], int]:
    """Lista della spesa con il totale esatto, solo per offerte esistenti."""
    by_id = {o.id: o for o in offers}
    lines = []
    for oid, qty in wanted.items():
        o = by_id.get(int(oid))
        q = int(qty)
        if o is None or q <= 0:
            continue
        lines.append(ShoppingLine(o.id, o.name, q, o.price_cents))
    return lines, sum(line.total_cents for line in lines)
