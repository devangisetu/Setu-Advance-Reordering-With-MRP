# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
from collections import defaultdict
from odoo.addons.stock.models.stock_rule import ProcurementException
from odoo.addons.stock.models.stock_rule import ProcurementGroup as pg

_logger = logging.getLogger(__name__)


def run_extended(self, procurements, raise_user_error=True):
    """Refined run method that supports mrp and subcontracting options."""
    if self._context.get('from_orderpoint'):
        self = self.with_context(custom_order_point_function=True)

    def raise_exception(procurement_errors):
        if raise_user_error:
            dummy, errors = zip(*procurement_errors)
            raise UserError('\n'.join(errors))
        else:
            raise ProcurementException(procurement_errors)

    actions_to_run = defaultdict(list)
    procurement_errors = []

    for procurement in procurements:
        procurement.values.setdefault('company_id', procurement.location_id.company_id)
        procurement.values.setdefault('priority', '0')
        procurement.values.setdefault('date_planned', fields.Datetime.now())
        if (
            procurement.product_id.type not in ('consu', 'combo') and procurement.product_id.is_storable == True or
            float_is_zero(procurement.product_qty, precision_rounding=procurement.product_uom.rounding)
        ):
            continue

        orderpoint = procurement.values.get('orderpoint_id', False)
        creation_option = orderpoint and orderpoint.document_creation_option or False

        if self._context.get('custom_order_point_function', False) and creation_option != 'od_default':
            if creation_option:
                if creation_option == 'ict':
                    actions_to_run['ict'].append(procurement)
                elif creation_option == 'iwt':
                    actions_to_run['iwt'].append(procurement)
                elif creation_option in ('po', 'subcontracting'):
                    domain = [('location_dest_id', '=', procurement.location_id.id), ('action', '=', 'buy')]
                    warehouse = procurement.values.get('warehouse_id', False)
                    if warehouse:
                        domain.append(('warehouse_id', '=', warehouse.id))
                    rule = self.env['stock.rule'].search(domain, order='route_sequence, sequence', limit=1)
                    if not rule:
                        error = _(
                            'No rule has been found to replenish "%s" in "%s".\nVerify the routes configuration '
                            'on the product.') % \
                                (procurement.product_id.display_name, procurement.location_id.display_name)
                        procurement_errors.append((procurement, error))
                    else:
                        action = rule.action
                        actions_to_run[action].append((procurement, rule))
                elif creation_option == 'mrp':
                    domain = [('location_dest_id', '=', procurement.location_id.id), ('action', '=', 'manufacture')]
                    warehouse = procurement.values.get('warehouse_id', False)
                    if warehouse:
                        domain.append(('warehouse_id', '=', warehouse.id))
                    rule = self.env['stock.rule'].search(domain, order='route_sequence, sequence', limit=1)
                    if not rule:
                        error = _(
                            'No rule has been found to manufacture "%s" in "%s".\nVerify the routes configuration '
                            'on the product.') % \
                                (procurement.product_id.display_name, procurement.location_id.display_name)
                        procurement_errors.append((procurement, error))
                    else:
                        action = rule.action
                        actions_to_run[action].append((procurement, rule))
                continue

        rule = self._get_rule(procurement.product_id, procurement.location_id, procurement.values)
        if not rule:
            error = _(
                'No rule has been found to replenish "%s" in "%s".\nVerify the routes configuration on the product.') % \
                    (procurement.product_id.display_name, procurement.location_id.display_name)
            procurement_errors.append((procurement, error))
        else:
            action = 'pull' if rule.action == 'pull_push' else rule.action
            actions_to_run[action].append((procurement, rule))

    if procurement_errors:
        raise_exception(procurement_errors)

    for action, procurements_to_run in actions_to_run.items():
        if hasattr(self.env['stock.rule'], '_run_%s' % action):
            try:
                getattr(self.env['stock.rule'], '_run_%s' % action)(procurements_to_run)
            except ProcurementException as e:
                procurement_errors += e.procurement_exceptions
        else:
            _logger.error("The method _run_%s doesn't exist on the procurement rules" % action)

    if procurement_errors:
        raise_exception(procurement_errors)
    return True

# Override the run method
pg.run = run_extended


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'
