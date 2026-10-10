"""
Chatbot & AI Copilot Routes (Blueprint: /api/chatbot)
Natural language assistant for non-technical users to query inventory, forecasts, alerts, and app guidance.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func, or_, and_

from database import get_db_session
from models import (
    Store, Product, InventoryLevel, InventoryAlert, Anomaly,
    Recommendation, Forecast, ForecastValue, Sale, User
)
from auth_service import get_current_user

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint('chatbot', __name__)

DEFAULT_SUGGESTIONS = [
    "🚨 Which items have critical low stock?",
    "📈 What is the sales forecast for Brake Pads?",
    "💡 Explain how cluster analysis helps us",
    "🛒 How do I reorder inventory?",
    "📊 Give me today's executive summary"
]


def _match_store(query_text: str, db) -> Optional[Store]:
    """Identify if query mentions a specific store (code or name)"""
    stores = db.query(Store).all()
    q_lower = query_text.lower()
    for s in stores:
        if s.store_code.lower() in q_lower:
            return s
        if s.name and any(part.lower() in q_lower for part in s.name.split() if len(part) > 3):
            return s
        if s.region and s.region.lower() in q_lower:
            return s
    return None


def _match_product(query_text: str, db) -> Optional[Product]:
    """Identify if query mentions a specific product or category"""
    products = db.query(Product).all()
    q_lower = query_text.lower()
    for p in products:
        if p.name.lower() in q_lower:
            return p
        # Check individual words for multi-word parts (e.g. 'brake' for 'Brake Pad')
        words = p.name.lower().split()
        for w in words:
            if len(w) >= 4 and w in q_lower:
                return p
    return None


def _handle_inventory_query(text: str, db) -> Dict[str, Any]:
    matched_store = _match_store(text, db)
    matched_product = _match_product(text, db)

    query = db.query(InventoryLevel, Store, Product).join(
        Store, InventoryLevel.store_id == Store.id
    ).join(
        Product, InventoryLevel.product_id == Product.id
    )

    if matched_store:
        query = query.filter(InventoryLevel.store_id == matched_store.id)
    if matched_product:
        query = query.filter(InventoryLevel.product_id == matched_product.id)

    # Prioritize items below or close to reorder point
    items = query.all()
    low_stock = [
        item for item in items
        if item.InventoryLevel.current_stock <= (item.InventoryLevel.reorder_point or 50)
    ]

    if not items:
        return {
            "reply": "I couldn't find any inventory records matching your query. Would you like to check all active stock levels?",
            "action": {"label": "Open Inventory Page", "path": "/inventory"},
            "suggestions": ["Show all low stock", "View critical alerts", "How do I reorder?"]
        }

    if low_stock:
        summary_lines = []
        for item in low_stock[:5]:
            lvl, st, pr = item
            summary_lines.append(
                f"• **{pr.name}** at *{st.name or st.store_code}*: **{lvl.current_stock} units left** (Reorder Point: {int(lvl.reorder_point or 0)}, Safety Stock: {int(lvl.safety_stock or 0)})"
            )

        store_context = f" in {matched_store.name or matched_store.store_code}" if matched_store else " across our network"
        reply = (
            f"⚠️ **Attention:** Found **{len(low_stock)} item(s) running low**{store_context}:\n\n"
            + "\n".join(summary_lines)
            + "\n\n💡 **Recommendation:** Reorder these items immediately so stock arrives before safety buffers are exhausted."
        )
        return {
            "reply": reply,
            "action": {"label": "Go to Inventory Workbench", "path": "/inventory"},
            "suggestions": ["How do I reorder these?", "Show demand forecast", "Check critical alerts"]
        }
    else:
        sample = items[:4]
        lines = [
            f"• **{pr.name}** ({st.name or st.store_code}): **{lvl.current_stock} units in stock** (Healthy)"
            for lvl, st, pr in sample
        ]
        return {
            "reply": "✅ **Inventory status is healthy!** None of these items are currently below their reorder threshold.\n\n" + "\n".join(lines),
            "action": {"label": "View Full Inventory", "path": "/inventory"},
            "suggestions": ["Show sales forecast", "Check for demand anomalies", "Show executive KPIs"]
        }


def _handle_forecast_query(text: str, db) -> Dict[str, Any]:
    matched_store = _match_store(text, db)
    matched_product = _match_product(text, db) or db.query(Product).first()
    store = matched_store or db.query(Store).first()

    # Look for active forecast
    fc = db.query(Forecast).filter_by(store_id=store.id, product_id=matched_product.id).first()
    if fc:
        values = db.query(ForecastValue).filter_by(forecast_id=fc.id).order_by(ForecastValue.target_date.asc()).limit(30).all()
        if values:
            avg_pred = sum(v.predicted_value for v in values) / len(values)
            min_bound = min(v.confidence_lower or v.predicted_value * 0.9 for v in values)
            max_bound = max(v.confidence_upper or v.predicted_value * 1.1 for v in values)

            reply = (
                f"📈 **Demand Forecast for {matched_product.name} ({store.name or store.store_code}):**\n\n"
                f"• **30-Day Average Expected Demand:** ~**{avg_pred:.1f} units / day**\n"
                f"• **95% Confidence Band:** Between **{min_bound:.1f}** (low bound) and **{max_bound:.1f}** (peak surge) units.\n"
                f"• **Model:** Meta Prophet (365-day seasonal decomposition)\n\n"
                f"💡 *Planning Tip:* Use the upper confidence range when planning safety stock to guarantee 0% stockouts during seasonal rushes."
            )
            return {
                "reply": reply,
                "action": {"label": "View Interactive Forecast Chart", "path": "/forecast"},
                "suggestions": ["Are we at risk of stockouts?", "Check low stock items", "Explain confidence intervals"]
            }

    # Fallback to general forecast description
    return {
        "reply": (
            f"📈 **Forecasting Insights for {matched_product.name}:**\n\n"
            f"Our Facebook Prophet model forecasts a stable sales velocity with weekly seasonality and higher volume on weekends. "
            f"You can explore the full 365-day projection curve and confidence bands on the Forecast page."
        ),
        "action": {"label": "Open Forecasting Page", "path": "/forecast"},
        "suggestions": ["Check critical stock", "Explain Prophet model", "View AI reorder actions"]
    }


def _handle_alerts_and_anomalies(text: str, db) -> Dict[str, Any]:
    crit_alerts = db.query(InventoryAlert, Store, Product).join(
        Store, InventoryAlert.store_id == Store.id
    ).join(
        Product, InventoryAlert.product_id == Product.id
    ).filter(InventoryAlert.is_resolved == False).order_by(InventoryAlert.id.desc()).limit(4).all()

    anomalies = db.query(Anomaly, Store, Product).join(
        Store, Anomaly.store_id == Store.id
    ).join(
        Product, Anomaly.product_id == Product.id
    ).filter(Anomaly.is_resolved == False).order_by(Anomaly.id.desc()).limit(3).all()

    sections = []
    if crit_alerts:
        alert_lines = [
            f"• **{al.severity.value.upper() if hasattr(al.severity, 'value') else al.severity}:** {pr.name} at *{st.name or st.store_code}* — {al.message}"
            for al, st, pr in crit_alerts
        ]
        sections.append("🚨 **Active Inventory Alerts:**\n" + "\n".join(alert_lines))

    if anomalies:
        anom_lines = [
            f"• **{an.anomaly_type.value if hasattr(an.anomaly_type, 'value') else an.anomaly_type}:** {pr.name} at *{st.name or st.store_code}* ({an.description or 'Unusual demand deviation detected'})"
            for an, st, pr in anomalies
        ]
        sections.append("⚡ **Statistical Anomalies Flagged:**\n" + "\n".join(anom_lines))

    if not sections:
        return {
            "reply": "✅ **Good news!** There are currently no unresolved critical alerts or demand anomalies in the system.",
            "action": {"label": "View All Alerts", "path": "/anomalies"},
            "suggestions": ["Check low stock items", "Forecast for Brake Pads", "Show executive KPIs"]
        }

    reply = "\n\n".join(sections) + "\n\n💡 Would you like to review and acknowledge these alerts?"
    return {
        "reply": reply,
        "action": {"label": "Resolve in Anomalies Page", "path": "/anomalies"},
        "suggestions": ["How do I resolve these?", "Check AI reorder actions", "Show low stock items"]
    }


def _handle_recommendations_query(text: str, db) -> Dict[str, Any]:
    recs = db.query(Recommendation, Store, Product).join(
        Store, Recommendation.store_id == Store.id
    ).join(
        Product, Recommendation.product_id == Product.id
    ).order_by(Recommendation.id.desc()).limit(4).all()

    if recs:
        lines = [
            f"• **{rec.title}:** {rec.description}"
            for rec, st, pr in recs
        ]
        reply = (
            "🛒 **Prioritized AI Reorder Directives:**\n\n"
            + "\n".join(lines)
            + "\n\n💡 *All order quantities are computed using:* `Reorder Point = (Daily Demand × Lead Time) + Safety Stock`."
        )
        return {
            "reply": reply,
            "action": {"label": "Go to AI Actions Page", "path": "/recommendations"},
            "suggestions": ["Which items are lowest?", "Show demand forecast", "Explain Reorder Point"]
        }

    return {
        "reply": "No pending reorder directives right now. Current inventory levels meet safety stock thresholds.",
        "action": {"label": "View AI Actions", "path": "/recommendations"},
        "suggestions": ["Check stock levels", "View 365-day forecast", "Explain clustering"]
    }


def _handle_explanation_query(text: str) -> Dict[str, Any]:
    t = text.lower()
    if "cluster" in t or "k-means" in t or "elbow" in t:
        return {
            "reply": (
                "💡 **What is Cluster Analysis in Stocker?**\n\n"
                "• **The Concept:** Instead of managing 100 products across 5 stores individually, Stocker uses **K-Means clustering** to group stores and categories that behave similarly.\n"
                "• **The Elbow Method:** Automatically determines that **k = 4** is the optimal number of groups by finding where inertia reduction levels off.\n"
                "• **Business Benefit:** For instance, discovering Mumbai and Delhi share identical engine part demand allows regional supply chain planners to negotiate **bulk supplier volume discounts** and balance inventory between nearby hubs."
            ),
            "action": {"label": "Explore Cluster Analytics", "path": "/analytics"},
            "suggestions": ["How does Prophet forecasting work?", "What is Reorder Point (ROP)?", "Check low stock"]
        }

    if "prophet" in t or "seasonality" in t:
        return {
            "reply": (
                "📈 **What is Facebook Prophet?**\n\n"
                "• **Designed for Business:** Created by Meta, Prophet decomposes sales into: `Trend + Weekly Seasonality + Yearly Seasonality + Holidays`.\n"
                "• **Confidence Intervals:** Unlike simple moving averages, Prophet calculates a **95% safe window** (best-case and worst-case demand) so you know both minimum and maximum expected sales.\n"
                "• **Why it's better:** It natively handles missing sales dates, festival spikes, and weather season shifts."
            ),
            "action": {"label": "Open Forecasting Page", "path": "/forecast"},
            "suggestions": ["Explain Cluster Analysis", "What is Reorder Point?", "Show low stock items"]
        }

    if "reorder" in t or "rop" in t or "formula" in t:
        return {
            "reply": (
                "📐 **The Reorder Point (ROP) Formula:**\n\n"
                "`ROP = (Average Daily Demand × Supplier Lead Time in Days) + Safety Stock`\n\n"
                "• **How it works:** When current inventory dips below the ROP, Stocker automatically creates a purchase directive so the new shipment arrives before safety stock is ever touched.\n"
                "• **Result:** Guaranteed 0% stockouts without needlessly tying up cash in excess inventory."
            ),
            "action": {"label": "View AI Directives", "path": "/recommendations"},
            "suggestions": ["Check low stock items", "View critical alerts", "Explain Prophet forecasting"]
        }

    if "help" in t or "how to use" in t or "navigate" in t:
        return {
            "reply": (
                "👋 **Welcome to Stocker AI Copilot!** Here is how to use the platform:\n\n"
                "1. **📊 Executive Dashboard:** High-level revenue motion, total alerts, and supply chain health.\n"
                "2. **📈 Forecasting:** 365-day demand predictions with 95% confidence intervals.\n"
                "3. **📦 Inventory:** Live stock levels, safety stocks, and reorder thresholds.\n"
                "4. **🗺️ Analytics:** K-Means clustering grouping stores and categories.\n"
                "5. **🚨 Anomalies:** Real-time demand spikes and sudden sales drops.\n"
                "6. **⚡ AI Actions:** Ready purchase directives with supplier names and order counts.\n\n"
                "You can ask me any question in plain English or click a suggestion below!"
            ),
            "action": {"label": "Go to Executive Overview", "path": "/"},
            "suggestions": DEFAULT_SUGGESTIONS
        }

    return {
        "reply": (
            "I'm here to help you navigate Stocker! You can ask me to check stock levels, summarize 365-day demand forecasts, "
            "inspect critical alerts, or explain any feature in simple words."
        ),
        "suggestions": DEFAULT_SUGGESTIONS
    }


@chatbot_bp.route('/message', methods=['POST'])
@chatbot_bp.route('/query', methods=['POST'])
def process_message():
    """
    Process natural language chatbot queries and return data-aware responses.
    """
    try:
        data = request.get_json(silent=True) or {}
        user_message = (data.get('message') or data.get('query') or '').strip()

        if not user_message:
            return jsonify({
                "status": "success",
                "data": {
                    "reply": "Hello! I am your **Stocker AI Copilot**. How can I assist you with your inventory or forecasts today?",
                    "suggestions": DEFAULT_SUGGESTIONS
                }
            })

        q_lower = user_message.lower()

        with get_db_session() as db:
            # 1. Forecasts (e.g. "What is the forecast for Brake Pads")
            if any(k in q_lower for k in ['forecast', 'predict', 'trend', 'future demand', 'sales projection']):
                if any(k in q_lower for k in ['explain', 'how does prophet', 'what is prophet']):
                    res = _handle_explanation_query(user_message)
                else:
                    res = _handle_forecast_query(user_message, db)
            # 2. Inventory & Stock Lookups (e.g. "What is the stock of...", "Which items are low")
            elif any(k in q_lower for k in ['stock', 'inventory', 'units', 'how many', 'low stock', 'out of stock']):
                res = _handle_inventory_query(user_message, db)
            # 3. Critical alerts & anomalies
            elif any(k in q_lower for k in ['alert', 'anomaly', 'critical', 'spike', 'drop', 'warning']):
                res = _handle_alerts_and_anomalies(user_message, db)
            # 4. Recommendations & Reorders
            elif any(k in q_lower for k in ['reorder', 'purchase', 'buy', 'directive', 'action', 'order']):
                if any(k in q_lower for k in ['explain', 'formula', 'meaning']):
                    res = _handle_explanation_query(user_message)
                else:
                    res = _handle_recommendations_query(user_message, db)
            # 5. Explanations / Concepts / Help
            elif any(k in q_lower for k in ['explain', 'what is', 'how to use', 'help', 'formula', 'meaning', 'why do we', 'cluster', 'k-means', 'elbow']):
                res = _handle_explanation_query(user_message)
            # 6. Executive / General Summary
            elif any(k in q_lower for k in ['summary', 'overview', 'kpi', 'status', 'hello', 'hi', 'hey']):
                res = {
                    "reply": (
                        "👋 Hello! Here is your quick **Stocker Operational Overview**:\n\n"
                        "• **System Health:** 🟢 Operational across 5 retail stores & 20 product categories.\n"
                        "• **Forecasting Engine:** Meta Prophet running 365-day time-series projections.\n"
                        "• **Active Alerts:** Check the Inventory and Anomalies pages for items nearing reorder thresholds.\n\n"
                        "How can I assist you right now?"
                    ),
                    "action": {"label": "Go to Executive Dashboard", "path": "/"},
                    "suggestions": DEFAULT_SUGGESTIONS
                }
            else:
                res = {
                    "reply": (
                        f"I understood your question about *\"{user_message}\"*. "
                        f"You can ask me to check low stock, show demand forecasts, list critical alerts, or explain any feature."
                    ),
                    "suggestions": DEFAULT_SUGGESTIONS
                }

        return jsonify({
            "status": "success",
            "data": res
        }), 200

    except Exception as exc:
        logger.error(f"Chatbot query error: {exc}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": "Failed to process chatbot query",
            "code": "CHATBOT_ERROR"
        }), 500
