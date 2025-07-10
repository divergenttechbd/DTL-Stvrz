import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Divider from '@mui/material/Divider';
import Typography from '@mui/material/Typography';
import ListItemText from '@mui/material/ListItemText';
import IconButton from '@mui/material/IconButton';
import Switch from '@mui/material/Switch'
// utils
import { IBookingItem } from 'src/types/booking';
// components
import Iconify from 'src/components/iconify';
import { format } from 'date-fns';
import upperFirst from 'lodash/upperFirst';
import { Button, Card, Tooltip } from '@mui/material';
import { useBoolean } from 'src/hooks/use-boolean';
import { getDecimalValue } from 'src/utils/format-number';

// ----------------------------------------------------------------------

type Props = {
  booking: IBookingItem;
};

export default function BookingDetailsContent({ booking }: Props) {
  const {
    status,
    night_count,
    guest_count,
    check_in,
    check_out,
    listing,
    paid_amount,
    price_info,
    price,
    host_pay_out,
    created_at,
    adult_count,
    children_count,
    infant_count,
    reservation_code,
    guest_service_charge,
    host_service_charge,
    applied_coupon_code,
    applied_coupon_type,
    discount_amount_applied,
  } = booking;

  console.log('booking', booking);

  const showPriceBreakdown = useBoolean();
  const showPriceBreakdownForHost = useBoolean();

  const guestCounts = [
    {
      type: adult_count > 1 ? 'adults' : 'adult',
      count: adult_count,
    },
    {
      type: children_count > 1 ? 'children' : 'child',
      count: children_count,
    },
    {
      type: infant_count > 1 ? 'infants' : 'infant',
      count: infant_count,
    },
  ].filter((data) => data.count);

  function formatDateRange(startDate: string, endDate: string): string {
    const start = new Date(startDate);
    const end = new Date(endDate);

    const startMonth = start.toLocaleString('default', { month: 'short' });
    const endMonth = end.toLocaleString('default', { month: 'short' });

    const startDateFormatted = `${startMonth} ${start.getDate()}`;
    const endDateFormatted =
      endMonth !== startMonth ? `${endMonth} ${end.getDate()}` : `${end.getDate()}`;

    return `${startDateFormatted}-${endDateFormatted}`;
  }

  const renderHead = (
    <>
      <Stack direction="column" sx={{ mb: 1 }}>
        <Typography variant="body2" sx={{ flexGrow: 1 }}>
          {upperFirst(status)}
        </Typography>
        <Typography variant="h3" sx={{ flexGrow: 1 }}>
          {listing.title}
        </Typography>
      </Stack>

      <Stack spacing={2} direction="row" flexWrap="wrap" alignItems="center" sx={{ mb: 1 }}>
        <Stack direction="row" alignItems="center" spacing={0.5} sx={{ typography: 'body2' }}>
          <Iconify icon="eva:star-fill" sx={{ color: 'warning.main' }} />
          <Box component="span" sx={{ typography: 'subtitle2' }}>
            {listing.avg_rating}
          </Box>
          <Link sx={{ color: 'text.secondary' }}>({listing.total_rating_count} reviews)</Link>
        </Stack>

        <Stack direction="row" alignItems="center" spacing={0.5} sx={{ typography: 'body2' }}>
          <Iconify icon="mingcute:location-fill" sx={{ color: 'error.main' }} />
          {listing.address}
        </Stack>
      </Stack>
      <Stack spacing={2} direction="row" flexWrap="wrap" sx={{ mb: 1 }}>
        <Typography variant="body2" sx={{ flexGrow: 1 }}>
          {formatDateRange(check_in, check_out)} ({guest_count} Guests)
        </Typography>
      </Stack>
      <Stack spacing={2} direction="row" flexWrap="wrap" sx={{ mb: 1 }}>
        <Typography variant="body2" sx={{ flexGrow: 1 }}>
          {guest_count} Guest • ৳{paid_amount}
        </Typography>
      </Stack>
    </>
  );

  const renderOverview = (
    <Box
      gap={3}
      display="grid"
      gridTemplateColumns={{
        xs: 'repeat(1, 1fr)',
        md: 'repeat(2, 1fr)',
      }}
    >
      {[
        {
          label: 'Guests',
          value: guestCounts.map((d) => `${d.count} ${d.type}`).join(', '),
          icon: <Iconify icon="solar:clock-circle-bold" />,
        },
        {
          label: 'Check-in',
          value: format(new Date(check_in), 'iii, MMM dd, yyyy'),
          icon: <Iconify icon="solar:clock-circle-bold" />,
        },
        {
          label: 'Checkout',
          value: format(new Date(check_out), 'iii, MMM dd, yyyy'),
          icon: <Iconify icon="solar:clock-circle-bold" />,
        },
        {
          label: 'Booking Date',
          value: format(new Date(created_at), 'iii, MMM dd, yyyy'),
          icon: <Iconify icon="solar:clock-circle-bold" />,
        },
        {
          label: 'Confirmation Code',
          value: reservation_code,
          icon: <Iconify icon="solar:clock-circle-bold" />,
        },
        {
          label: `Cancellation Policy (${listing.cancellation_policy.policy_name})`,
          value: listing.cancellation_policy.description,
          icon: <Iconify icon="solar:clock-circle-bold" />,
        },
      ].map((item) => (
        <Stack key={item.label} spacing={1.5} direction="row">
          {item.icon}
          <ListItemText
            primary={item.label}
            secondary={item.value}
            primaryTypographyProps={{
              typography: 'body2',
              color: 'text.secondary',
              mb: 0.5,
            }}
            secondaryTypographyProps={{
              typography: 'subtitle2',
              color: 'text.primary',
              component: 'span',
            }}
          />
        </Stack>
      ))}
    </Box>
  );

  const priceBreakdown = Object.keys(price_info || {})
    .sort()
    .map((key) => (
      <Stack direction="row" key={key} justifyContent="space-between">
        <Typography>{key}</Typography>
        <Typography>৳ {price_info[key].price}</Typography>
      </Stack>
    ));

  const renderContent = (
    <Stack spacing={2}>
      <Box
        rowGap={2}
        gap={3}
        display="grid"
        gridTemplateColumns={{
          xs: 'repeat(1, 1fr)',
          md: 'repeat(2, 1fr)',
        }}
      >
        <Card sx={{ padding: 3 }}>
          <Typography variant="h6" sx={{ marginBottom: 3 }}>
            Guest Paid
          </Typography>
          <Stack key="Guest Paid" spacing={1} direction="column">
            <Stack direction="row" justifyContent="space-between">
              <Typography>
                ৳{price_info[Object.keys(price_info)[0]].price} × {night_count} nights
              </Typography>
              <Typography>৳{getDecimalValue(price)}</Typography>
            </Stack>
            {showPriceBreakdown.value && priceBreakdown}
            <Stack direction="row" justifyContent="space-between">
              <Typography
                sx={{ fontWeight: 'medium', textDecoration: 'underline', cursor: 'pointer' }}
                display="inline"
                onClick={showPriceBreakdown.onToggle}
              >
                {showPriceBreakdown.value ? 'Hide Breakdown' : 'Show Breakdown'}
              </Typography>
            </Stack>
            <Stack
              direction="row"
              justifyContent="space-between"
            >
              <Typography>
                Applied Coupon {applied_coupon_code ? `(${applied_coupon_code})` : ''}
                {applied_coupon_type ?
                  <Tooltip title={`Coupon Type: ${applied_coupon_type}`} placement="top">
                    <IconButton color="primary">
                      <Iconify sx={{ transform: "rotate(180deg)" }} icon="mdi:exclamation" />
                    </IconButton>
                  </Tooltip> : ''}
              </Typography>

              <Typography>৳{getDecimalValue(Number(discount_amount_applied))}</Typography>
            </Stack>
            <Stack
              direction="row"
              justifyContent="space-between"
              sx={{ borderBottom: 1, paddingBottom: 2 }}
            >
              <Typography>Guest Service Charge</Typography>
              <Typography>৳{getDecimalValue(guest_service_charge)}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography>Guest Paid</Typography>
              <Typography>৳{Math.round(paid_amount)}</Typography>
            </Stack>
          </Stack>
        </Card>
        <Card sx={{ padding: 3 }}>
          <Typography variant="h6" sx={{ marginBottom: 3 }}>
            Host Payout
          </Typography>
          <Stack key="Host Paid" spacing={1} direction="column">
            <Stack direction="row" justifyContent="space-between">
              <Typography>
                ৳{price_info[Object.keys(price_info)[0]].price} × {night_count} nights
              </Typography>
              <Typography>৳{getDecimalValue(price)}</Typography>
            </Stack>
            {showPriceBreakdownForHost.value && priceBreakdown}
            <Stack direction="row" justifyContent="space-between">
              <Typography
                sx={{ fontWeight: 'medium', textDecoration: 'underline', cursor: 'pointer' }}
                display="inline"
                onClick={showPriceBreakdownForHost.onToggle}
              >
                {showPriceBreakdownForHost.value ? 'Hide Breakdown' : 'Show Breakdown'}
              </Typography>
            </Stack>
            <Stack
              direction="row"
              justifyContent="space-between"
              sx={{ borderBottom: 1, paddingBottom: 2 }}
            >
              <Typography>Host Service Charge</Typography>
              <Typography>৳{getDecimalValue(host_service_charge)}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography>Host Payout</Typography>
              <Typography>৳{Math.round(host_pay_out)}</Typography>
            </Stack>
          </Stack>
        </Card>
      </Box>
    </Stack>
  );

  // const toggleInstantBooking = useCallback(async () => {
  //   try {
  //     const res = await updateUser({
  //       id: booking?.id,
  //       user_status: booking?.status === 'active' ? 'restricted' : 'active',
  //     });
  //     if (!res.success) throw res.data;
  //     getUserDetails?.();
  //     setVerificationAction('');
  //   } catch (err) {
  //     console.log(err);
  //   }
  // }, [currentUser?.id, currentUser?.status, getUserDetails]);

  return (
    <Stack sx={{ maxWidth: 720, mx: 'auto' }}>
      {renderHead}

      <Divider sx={{ borderStyle: 'dashed', my: 5 }} />

      <Typography variant="h6" sx={{ marginBottom: 3 }}>
        Overview
      </Typography>
      {renderOverview}

      <Divider sx={{ borderStyle: 'dashed', my: 5 }} />

      {renderContent}
    </Stack >
  );
}
