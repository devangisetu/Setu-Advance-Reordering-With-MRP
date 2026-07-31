DROP FUNCTION IF EXISTS public.get_product_subcontract_history(integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_product_subcontract_history(
    IN orderpoint_ids integer[],
    IN start_date date,
    IN end_date date
)
RETURNS TABLE(
    orderpoint_id integer,
    product_id integer,
    warehouse_id integer,
    purchase_id integer,
    partner_id integer,
    currency_id integer,
    purchase_price numeric,
    po_qty numeric,
    po_date date,
    lead_time integer
) AS
$BODY$
BEGIN
    RETURN QUERY
    WITH moves_info AS (
        SELECT 
            op.id AS orderpoint_id,
            sm.product_id,
            COALESCE(
                sm.warehouse_id,
                spt.warehouse_id,
                dest_wh.id,
                source_wh.id
            ) AS wh_id,
            po.id AS purchase_id,
            po.partner_id,
            po.currency_id,
            pol.price_unit AS purchase_price,
            sm.product_qty,
            sm.date AS move_date,
            po.date_order
        FROM stock_move sm
        INNER JOIN purchase_order_line pol ON pol.id = sm.purchase_line_id
        INNER JOIN purchase_order po ON po.id = pol.order_id
        INNER JOIN product_product pp ON pp.id = sm.product_id
        INNER JOIN product_template pt ON pt.id = pp.product_tmpl_id
        INNER JOIN stock_warehouse_orderpoint op ON op.product_id = sm.product_id
        LEFT JOIN stock_picking_type spt ON spt.id = sm.picking_type_id
        LEFT JOIN stock_location source_loc ON source_loc.id = sm.location_id
        LEFT JOIN stock_location dest_loc ON dest_loc.id = sm.location_dest_id
        LEFT JOIN stock_warehouse source_wh ON source_loc.parent_path::text ~~ concat('%/', source_wh.view_location_id, '/%')
        LEFT JOIN stock_warehouse dest_wh ON dest_loc.parent_path::text ~~ concat('%/', dest_wh.view_location_id, '/%')
        WHERE sm.state = 'done'
          AND op.id = ANY(orderpoint_ids)
          AND op.warehouse_id = COALESCE(
              sm.warehouse_id,
              spt.warehouse_id,
              dest_wh.id,
              source_wh.id
          )
          AND sm.date::date >= start_date
          AND sm.date::date <= end_date
          AND (
              sm.is_subcontract = TRUE
              OR EXISTS (
                  SELECT 1 FROM mrp_bom bom
                  JOIN mrp_bom_subcontractor boms ON boms.mrp_bom_id = bom.id
                  JOIN res_partner vendor ON vendor.id = po.partner_id
                  WHERE bom.type = 'subcontract'
                    AND (boms.res_partner_id = vendor.id OR boms.res_partner_id = vendor.commercial_partner_id)
                    AND (
                        bom.product_id = sm.product_id
                        OR (bom.product_tmpl_id = pt.id AND bom.product_id IS NULL)
                    )
              )
          )
    )
    SELECT 
        m.orderpoint_id,
        m.product_id,
        m.wh_id AS warehouse_id,
        m.purchase_id,
        m.partner_id,
        m.currency_id,
        m.purchase_price::numeric,
        SUM(m.product_qty)::numeric AS po_qty,
        m.date_order::date AS po_date,
        COALESCE(EXTRACT(DAY FROM (MAX(m.move_date) - m.date_order))::integer + 1, 0) AS lead_time
    FROM moves_info m
    GROUP BY 
        m.orderpoint_id,
        m.product_id,
        m.wh_id,
        m.purchase_id,
        m.partner_id,
        m.currency_id,
        m.purchase_price,
        m.date_order;

END; $BODY$
LANGUAGE plpgsql VOLATILE
COST 100
ROWS 1000;
