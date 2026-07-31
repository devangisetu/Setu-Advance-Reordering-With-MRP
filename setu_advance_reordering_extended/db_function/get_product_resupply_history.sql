DROP FUNCTION IF EXISTS public.get_product_resupply_history(integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_product_resupply_history(
    IN orderpoint_ids integer[],
    IN start_date_val date,
    IN end_date_val date
)
RETURNS TABLE(
    orderpoint_id integer,
    product_id integer,
    warehouse_id integer,
    start_date date,
    end_date date,
    duration integer,
    resupply_qty numeric,
    total_resupply_qty numeric,
    average_daily_resupply numeric,
    total_resupply_orders integer,
    maximum_daily_resupply numeric,
    minimum_daily_resupply numeric
) AS
$BODY$
BEGIN
    RETURN QUERY
    WITH periods AS (
        SELECT 
            id AS period_id,
            fpstartdate AS p_start,
            fpenddate AS p_end,
            COALESCE(NULLIF((fpenddate - fpstartdate) + 1, 0), 1) AS p_duration
        FROM reorder_fiscalperiod
        WHERE fpstartdate >= start_date_val AND fpstartdate <= end_date_val
    ),
    orderpoints AS (
        SELECT 
            op.id AS orderpoint_id,
            op.product_id,
            op.warehouse_id,
            op.company_id
        FROM stock_warehouse_orderpoint op
        WHERE op.id = ANY(orderpoint_ids)
    ),
    op_periods AS (
        SELECT 
            op.orderpoint_id,
            op.product_id,
            op.warehouse_id,
            op.company_id,
            p.period_id,
            p.p_start,
            p.p_end,
            p.p_duration
        FROM orderpoints op
        CROSS JOIN periods p
    ),
    raw_moves AS (
        SELECT 
            sm.id AS move_id,
            sm.product_id,
            sm.product_qty,
            sm.date::date AS move_date,
            sm.picking_id,
            COALESCE(
                sm.warehouse_id,
                spt.warehouse_id,
                dest_wh.id,
                source_wh.id,
                (
                    SELECT op.warehouse_id 
                    FROM stock_warehouse_orderpoint op 
                    WHERE op.product_id = sm.product_id 
                      AND op.company_id = sm.company_id 
                    LIMIT 1
                )
            ) AS wh_id
        FROM stock_move sm
        INNER JOIN stock_picking sp ON sp.id = sm.picking_id
        INNER JOIN stock_location dest_loc ON dest_loc.id = sp.location_dest_id
        LEFT JOIN stock_picking_type spt ON spt.id = sm.picking_type_id
        LEFT JOIN stock_location source_loc ON source_loc.id = sm.location_id
        LEFT JOIN stock_location d_loc ON d_loc.id = sm.location_dest_id
        LEFT JOIN stock_warehouse source_wh ON source_loc.parent_path::text ~~ concat('%/', source_wh.view_location_id, '/%')
        LEFT JOIN stock_warehouse dest_wh ON d_loc.parent_path::text ~~ concat('%/', dest_wh.view_location_id, '/%')
        WHERE sm.state = 'done'
          AND sm.picking_id IS NOT NULL
          AND dest_loc.is_subcontracting_location = TRUE
          AND sm.product_id IN (SELECT op.product_id FROM orderpoints op)
    ),
    daily_totals AS (
        SELECT 
            op.orderpoint_id,
            op.period_id,
            rm.move_date,
            SUM(rm.product_qty) AS daily_qty
        FROM op_periods op
        INNER JOIN raw_moves rm ON rm.product_id = op.product_id AND rm.wh_id = op.warehouse_id
        WHERE rm.move_date >= op.p_start AND rm.move_date <= op.p_end
        GROUP BY 
            op.orderpoint_id,
            op.period_id,
            rm.move_date
    ),
    period_pickings AS (
        SELECT 
            op.orderpoint_id,
            op.period_id,
            COUNT(DISTINCT rm.picking_id) AS total_resupply_orders
        FROM op_periods op
        INNER JOIN raw_moves rm ON rm.product_id = op.product_id AND rm.wh_id = op.warehouse_id
        WHERE rm.move_date >= op.p_start AND rm.move_date <= op.p_end
        GROUP BY 
            op.orderpoint_id,
            op.period_id
    ),
    period_metrics AS (
        SELECT 
            dt.orderpoint_id,
            dt.period_id,
            SUM(dt.daily_qty) AS total_resupply,
            MAX(dt.daily_qty) AS max_daily,
            MIN(NULLIF(dt.daily_qty, 0)) AS min_daily
        FROM daily_totals dt
        GROUP BY 
            dt.orderpoint_id,
            dt.period_id
    )
    SELECT 
        op.orderpoint_id,
        op.product_id,
        op.warehouse_id,
        op.p_start AS start_date,
        op.p_end AS end_date,
        op.p_duration AS duration,
        COALESCE(pm.total_resupply, 0.0)::numeric AS resupply_qty,
        COALESCE(pm.total_resupply, 0.0)::numeric AS total_resupply_qty,
        ROUND(COALESCE(pm.total_resupply, 0.0) / op.p_duration, 2)::numeric AS average_daily_resupply,
        COALESCE(pp.total_resupply_orders, 0)::integer AS total_resupply_orders,
        COALESCE(pm.max_daily, 0.0)::numeric AS maximum_daily_resupply,
        COALESCE(pm.min_daily, 0.0)::numeric AS minimum_daily_resupply
    FROM op_periods op
    LEFT JOIN period_metrics pm ON pm.orderpoint_id = op.orderpoint_id AND pm.period_id = op.period_id
    LEFT JOIN period_pickings pp ON pp.orderpoint_id = op.orderpoint_id AND pp.period_id = op.period_id;

END; $BODY$
LANGUAGE plpgsql VOLATILE
COST 100
ROWS 1000;
