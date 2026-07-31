DROP FUNCTION IF EXISTS public.get_product_production_history(integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_product_production_history(
    IN orderpoint_ids integer[],
    IN start_date_val date,
    IN end_date_val date
)
RETURNS TABLE(
    orderpoint_id integer,
    product_id integer,
    warehouse_id integer,
    production_id integer,
    mo_date date,
    produced_qty numeric,
    lead_time integer
) AS
$BODY$
BEGIN
    RETURN QUERY
    WITH orderpoints AS (
        SELECT 
            op.id AS orderpoint_id,
            op.product_id,
            op.warehouse_id
        FROM stock_warehouse_orderpoint op
        WHERE op.id = ANY(orderpoint_ids)
    ),
    mo_info AS (
        SELECT 
            op.orderpoint_id,
            mo.product_id,
            op.warehouse_id,
            mo.id AS mo_id,
            mo.date_finished::date AS mo_date,
            COALESCE((
                SELECT SUM(sm.product_qty) 
                FROM stock_move sm 
                WHERE sm.production_id = mo.id 
                  AND sm.product_id = mo.product_id 
                  AND sm.state = 'done'
            ), 0.0) AS produced_qty,
            COALESCE(
                GREATEST(0, EXTRACT(DAY FROM (mo.date_finished - COALESCE(mo.date_start, mo.create_date)))::integer + 1),
                0
            ) AS lead_time
        FROM mrp_production mo
        INNER JOIN stock_picking_type spt ON spt.id = mo.picking_type_id
        INNER JOIN orderpoints op ON op.product_id = mo.product_id AND op.warehouse_id = spt.warehouse_id
        WHERE mo.state = 'done'
          AND mo.date_finished::date >= start_date_val
          AND mo.date_finished::date <= end_date_val
    )
    SELECT 
        m.orderpoint_id,
        m.product_id,
        m.warehouse_id,
        m.mo_id AS production_id,
        m.mo_date,
        m.produced_qty::numeric,
        m.lead_time::integer
    FROM mo_info m;

END; $BODY$
LANGUAGE plpgsql VOLATILE
COST 100
ROWS 1000;
