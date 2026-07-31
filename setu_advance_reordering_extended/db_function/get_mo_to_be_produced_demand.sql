DROP FUNCTION IF EXISTS public.get_mo_to_be_produced_demand(integer[], integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_mo_to_be_produced_demand(
    IN product_ids integer[],
    IN warehouse_ids integer[],
    IN start_date date,
    IN end_date date)
    RETURNS TABLE(
        mo_id integer,
        mo_main_product_id integer,
        product_id integer,
        required_qty numeric
    ) AS
$BODY$
BEGIN
    RETURN QUERY
    SELECT
        mp.id AS mo_id,
        mp.product_id AS mo_main_product_id,
        mp.product_id AS product_id,
        COALESCE(mp.product_qty, 0) AS required_qty
    FROM mrp_production mp
        LEFT JOIN stock_picking_type spt ON spt.id = mp.picking_type_id
    WHERE mp.state = 'draft'
        AND mp.date_start IS NOT NULL
        AND mp.date_finished IS NOT NULL
        AND mp.date_start::date >= start_date
        AND mp.date_finished::date <= end_date
        AND (
            COALESCE(array_length(product_ids, 1), 0) < 1
            OR mp.product_id = ANY(product_ids)
        )
        AND (
            COALESCE(array_length(warehouse_ids, 1), 0) < 1
            OR spt.warehouse_id = ANY(warehouse_ids)
        );
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;
