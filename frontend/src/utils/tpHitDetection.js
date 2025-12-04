/**
 * TP Hit Detection Utility
 * 
 * Extracts TP hit status from trade group webhooks.
 * **Feature: trade-enhancements, Property 10: TP Hit Detection**
 * **Feature: trade-enhancements, Property 11: All TPs Complete Detection**
 */

/**
 * @typedef {Object} TPHitInfo
 * @property {string} level - TP level (TP1, TP2, TP3)
 * @property {boolean} isHit - Whether this TP level was hit
 * @property {string|null} timestamp - ISO timestamp when TP was hit
 * @property {number|null} exitPrice - Exit price when TP was hit
 * @property {number|null} pnlPercent - P&L percentage for this TP exit
 * @property {number|null} quantity - Quantity sold at this TP
 * @property {number|null} positionPercent - Percentage of total position sold at this TP
 */

/**
 * @typedef {Object} TPHitStatus
 * @property {boolean} tp1Hit - Whether TP1 was hit
 * @property {string|null} tp1Timestamp - Timestamp when TP1 was hit
 * @property {number|null} tp1Price - Exit price for TP1
 * @property {number|null} tp1PnlPercent - P&L percentage for TP1
 * @property {boolean} tp2Hit - Whether TP2 was hit
 * @property {string|null} tp2Timestamp - Timestamp when TP2 was hit
 * @property {number|null} tp2Price - Exit price for TP2
 * @property {number|null} tp2PnlPercent - P&L percentage for TP2
 * @property {boolean} tp3Hit - Whether TP3 was hit
 * @property {string|null} tp3Timestamp - Timestamp when TP3 was hit
 * @property {number|null} tp3Price - Exit price for TP3
 * @property {number|null} tp3PnlPercent - P&L percentage for TP3
 * @property {boolean} allTpsComplete - Whether all configured TPs have been hit
 * @property {TPHitInfo[]} tpDetails - Array of TP hit details
 */

/**
 * Determines the action type from a webhook/trade entry.
 * This mirrors the logic in TradeGroupsView for consistency.
 * 
 * @param {Object} webhook - The webhook/trade object
 * @returns {string} - Action type (Entry, TP1, TP2, TP3, SL Close, etc.)
 */
export function determineActionType(webhook) {
  // Use tp_level from backend if available
  if (webhook.tp_level) {
    if (webhook.tp_level === 'ENTRY') return 'Entry'
    if (webhook.tp_level === 'TP1') return 'TP1'
    if (webhook.tp_level === 'TP2') return 'TP2'
    if (webhook.tp_level === 'TP3') return 'TP3'
    if (webhook.tp_level === 'SL') return 'SL Close'
    if (webhook.tp_level === 'PARTIAL') return 'Partial'
  }

  // Fallback to manual detection from metadata
  const comment = webhook.metadata?.order_comment?.toLowerCase() || ''
  const orderId = webhook.metadata?.order_id?.toLowerCase() || ''
  const alertMessage = webhook.metadata?.alert_message_params?.order_type?.toLowerCase() || ''

  if (alertMessage.includes('enter_long') || alertMessage.includes('enter_short')) {
    return 'Entry'
  }
  if (comment.includes('tp1') || orderId.includes('1st target')) return 'TP1'
  if (comment.includes('tp2') || orderId.includes('2nd target')) return 'TP2'
  if (comment.includes('tp3') || orderId.includes('3rd target')) return 'TP3'
  if (comment.includes('sl') || comment.includes('stop loss')) return 'SL Close'
  if (alertMessage.includes('reduce')) return 'Partial'
  if (webhook.action === 'buy' && !comment) return 'Entry'
  return 'Close'
}

/**
 * Extracts TP hit status from trade group webhooks.
 * 
 * **Validates: Requirements 3.2, 3.5**
 * 
 * @param {Object[]} trades - Array of webhook/trade objects in a trade group
 * @returns {TPHitStatus} - Object containing TP hit flags and details
 */
export function getTPHitStatus(trades) {
  if (!trades || !Array.isArray(trades) || trades.length === 0) {
    return {
      tp1Hit: false,
      tp1Timestamp: null,
      tp1Price: null,
      tp1PnlPercent: null,
      tp2Hit: false,
      tp2Timestamp: null,
      tp2Price: null,
      tp2PnlPercent: null,
      tp3Hit: false,
      tp3Timestamp: null,
      tp3Price: null,
      tp3PnlPercent: null,
      allTpsComplete: false,
      tpDetails: [],
      entryQuantity: null
    }
  }

  // Find entry quantity from the entry trade
  let entryQuantity = null
  for (const trade of trades) {
    const actionType = determineActionType(trade)
    if (actionType === 'Entry') {
      entryQuantity = trade.quantity || trade.metadata?.order_contracts || null
      if (entryQuantity) entryQuantity = parseFloat(entryQuantity)
      break
    }
  }

  const result = {
    tp1Hit: false,
    tp1Timestamp: null,
    tp1Price: null,
    tp1PnlPercent: null,
    tp2Hit: false,
    tp2Timestamp: null,
    tp2Price: null,
    tp2PnlPercent: null,
    tp3Hit: false,
    tp3Timestamp: null,
    tp3Price: null,
    tp3PnlPercent: null,
    allTpsComplete: false,
    tpDetails: [],
    entryQuantity
  }

  // Process each trade to find TP hits
  for (const trade of trades) {
    const actionType = determineActionType(trade)
    const exitPrice = trade.price || trade.metadata?.order_price || null
    const timestamp = trade.timestamp || null
    const pnlPercent = trade.realized_pnl_percent ?? null
    const quantity = trade.quantity || trade.metadata?.order_contracts || null
    const quantityNum = quantity ? parseFloat(quantity) : null
    const positionPercent = (entryQuantity && quantityNum) 
      ? (quantityNum / entryQuantity) * 100 
      : null

    if (actionType === 'TP1' && !result.tp1Hit) {
      result.tp1Hit = true
      result.tp1Timestamp = timestamp
      result.tp1Price = exitPrice
      result.tp1PnlPercent = pnlPercent
      result.tpDetails.push({
        level: 'TP1',
        isHit: true,
        timestamp,
        exitPrice,
        pnlPercent,
        quantity: quantityNum,
        positionPercent
      })
    } else if (actionType === 'TP2' && !result.tp2Hit) {
      result.tp2Hit = true
      result.tp2Timestamp = timestamp
      result.tp2Price = exitPrice
      result.tp2PnlPercent = pnlPercent
      result.tpDetails.push({
        level: 'TP2',
        isHit: true,
        timestamp,
        exitPrice,
        pnlPercent,
        quantity: quantityNum,
        positionPercent
      })
    } else if (actionType === 'TP3' && !result.tp3Hit) {
      result.tp3Hit = true
      result.tp3Timestamp = timestamp
      result.tp3Price = exitPrice
      result.tp3PnlPercent = pnlPercent
      result.tpDetails.push({
        level: 'TP3',
        isHit: true,
        timestamp,
        exitPrice,
        pnlPercent,
        quantity: quantityNum,
        positionPercent
      })
    }
  }

  // Add non-hit TPs to details
  if (!result.tp1Hit) {
    result.tpDetails.push({ level: 'TP1', isHit: false, timestamp: null, exitPrice: null, pnlPercent: null, quantity: null, positionPercent: null })
  }
  if (!result.tp2Hit) {
    result.tpDetails.push({ level: 'TP2', isHit: false, timestamp: null, exitPrice: null, pnlPercent: null, quantity: null, positionPercent: null })
  }
  if (!result.tp3Hit) {
    result.tpDetails.push({ level: 'TP3', isHit: false, timestamp: null, exitPrice: null, pnlPercent: null, quantity: null, positionPercent: null })
  }

  // Sort tpDetails by level
  result.tpDetails.sort((a, b) => a.level.localeCompare(b.level))

  // Check if all TPs are complete
  // **Property 11: All TPs Complete Detection**
  // For any trade group where TP1, TP2, and TP3 are all marked as hit, 
  // the allTpsComplete flag shall be true.
  result.allTpsComplete = result.tp1Hit && result.tp2Hit && result.tp3Hit

  return result
}

/**
 * Gets a formatted tooltip message for a TP level.
 * 
 * @param {TPHitInfo} tpInfo - TP hit info object
 * @returns {string} - Formatted tooltip message
 */
export function getTPTooltipMessage(tpInfo) {
  if (!tpInfo.isHit) {
    return `${tpInfo.level}: Not hit`
  }

  const parts = [`${tpInfo.level}: Hit ✓`]
  
  if (tpInfo.timestamp) {
    const date = new Date(tpInfo.timestamp)
    parts.push(`Time: ${date.toLocaleString()}`)
  }
  
  if (tpInfo.exitPrice !== null && tpInfo.exitPrice !== undefined) {
    parts.push(`Price: ${parseFloat(tpInfo.exitPrice).toFixed(4)}`)
  }
  
  // Show quantity and position percentage
  if (tpInfo.quantity !== null && tpInfo.quantity !== undefined) {
    let qtyStr = `Qty: ${tpInfo.quantity.toFixed(2)}`
    if (tpInfo.positionPercent !== null && tpInfo.positionPercent !== undefined) {
      qtyStr += ` (${tpInfo.positionPercent.toFixed(1)}% of position)`
    }
    parts.push(qtyStr)
  }
  
  if (tpInfo.pnlPercent !== null && tpInfo.pnlPercent !== undefined) {
    const sign = tpInfo.pnlPercent >= 0 ? '+' : ''
    parts.push(`P&L: ${sign}${tpInfo.pnlPercent.toFixed(2)}%`)
  }

  return parts.join('\n')
}
