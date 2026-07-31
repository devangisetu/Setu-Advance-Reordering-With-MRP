DROP FUNCTION IF EXISTS public.update_product_scrap_history(integer[], date, date, integer);
CREATE OR REPLACE FUNCTION public.update_product_scrap_history(
    IN orderpoint_ids integer[],
    IN start_date_val date,
    IN end_date_val date,
    IN uid integer
)
RETURNS void AS
$BODY$
BEGIN
    -- Delete existing records for these orderpoints
    DELETE FROM product_scrap_history
    WHERE orderpoint_id = ANY(orderpoint_ids);

    -- Insert new history records
    INSERT INTO product_scrap_history (
        orderpoint_id,
        product_id,
        warehouse_id,
        start_date,
        end_date,
        duration,
        scrap_qty,
        average_daily_scrap,
        maximum_daily_scrap,
        minimum_daily_scrap,
        create_uid,
        write_uid,
        create_date,
        write_date
    )
    SELECT 
        res.orderpoint_id,
        res.product_id,
        res.warehouse_id,
        res.start_date,
        res.end_date,
        res.duration,
        res.scrap_qty,
        res.average_daily_scrap,
        res.maximum_daily_scrap,
        res.minimum_daily_scrap,
        uid,
        uid,
        now() AT TIME ZONE 'UTC',
        now() AT TIME ZONE 'UTC'
    FROM get_product_scrap_history(orderpoint_ids, start_date_val, end_date_val) res;

END; $BODY$
LANGUAGE plpgsql VOLATILE
COST 100;
