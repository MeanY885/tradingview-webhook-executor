"""Webhook logs routes for frontend."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.webhook_log import WebhookLog
from app.extensions import db
from sqlalchemy import desc, func

bp = Blueprint('webhook_logs', __name__, url_prefix='/api/webhook-logs')


@bp.route('', methods=['GET'])
@jwt_required()
def get_webhook_logs():
    """Get webhook logs for current user with filtering."""
    user_id = get_jwt_identity()

    # Query params
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    broker = request.args.get('broker')
    status = request.args.get('status')
    symbol = request.args.get('symbol')

    # Build query
    query = WebhookLog.query.filter_by(user_id=user_id)

    if broker:
        query = query.filter_by(broker=broker)
    if status:
        query = query.filter_by(status=status)
    if symbol:
        query = query.filter(WebhookLog.symbol.ilike(f'%{symbol}%'))

    # Paginate
    pagination = query.order_by(desc(WebhookLog.timestamp)).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return jsonify({
        'logs': [log.to_dict() for log in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })


@bp.route('/stats', methods=['GET'])
@jwt_required()
def get_webhook_stats():
    """Get statistics for current user."""
    user_id = get_jwt_identity()

    # Count by status
    stats = db.session.query(
        WebhookLog.status,
        func.count(WebhookLog.id).label('count')
    ).filter_by(user_id=user_id).group_by(WebhookLog.status).all()

    return jsonify({
        'by_status': {stat.status: stat.count for stat in stats}
    })
