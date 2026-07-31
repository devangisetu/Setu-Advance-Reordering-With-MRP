DROP FUNCTION IF EXISTS public.update_product_production_history(integer[], date, date, integer);
CREATE OR REPLACE FUNCTION public.update_product_production_history(
    IN orderpoint_ids integer[],
    IN start_date date,
    IN end_date date,
    IN uid integer
)
RETURNS void AS
$BODY$
BEGIN
    -- Delete existing records for these orderpoints
    DELETE FROM product_production_history
    WHERE orderpoint_id = ANY(orderpoint_ids);

    -- Insert new history records
    INSERT INTO product_production_history (
        orderpoint_id,
        product_id,
        warehouse_id,
        production_id,
        mo_date,
        produced_qty,
        lead_time,
        create_uid,
        write_uid,
        create_date,
        write_date
    )
    SELECT 
        res.orderpoint_id,
        res.product_id,
        res.warehouse_id,
        res.production_id,
        res.mo_date,
        res.produced_qty,
        res.lead_time,
        uid,
        uid,
        now() AT TIME ZONE 'UTC',
        now() AT TIME ZONE 'UTC'
    FROM get_product_production_history(orderpoint_ids, start_date, end_date) res;

END; $BODY$
LANGUAGE plpgsql VOLATILE
COST 100;
