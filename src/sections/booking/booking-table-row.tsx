// @mui
import Button from '@mui/material/Button';
import Tooltip from '@mui/material/Tooltip';
import TableRow from '@mui/material/TableRow';
import Checkbox from '@mui/material/Checkbox';
import TableCell from '@mui/material/TableCell';
import ListItemText from '@mui/material/ListItemText';
import Box from '@mui/material/Box'
import Divider from '@mui/material/Divider'
// hooks
import { useRouter } from 'src/routes/hook';
import { format } from 'date-fns';
import { IBookingItem } from 'src/types/booking';
import { Link } from '@mui/material';
import { paths } from 'src/routes/paths';
import { getDecimalValue } from 'src/utils/format-number';
//
import Iconify from 'src/components/iconify';
import React from 'react';

type Props = {
  selected: boolean;
  onEditRow: VoidFunction;
  row: IBookingItem;
  onSelectRow: VoidFunction;
  onDeleteRow: VoidFunction;
  onCancel: VoidFunction;
};

export default function BookingTableRow({
  row,
  selected,
  onEditRow,
  onSelectRow,
  onDeleteRow,
  onCancel,
}: Props) {
  const {
    id,
    check_in,
    check_out,
    created_at,
    listing,
    reservation_code,
    paid_amount,
    guest,
    host,
    adult_count,
    children_count,
    infant_count,
    reviews,
  } = row;

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

  const router = useRouter();

  const today = new Date().toISOString().split('T')[0];

  const isDuringStay = today >= check_in && today <= check_out;

  console.log("is during stay", isDuringStay)

  return (
    <TableRow hover selected={selected}>
      <TableCell padding="checkbox">
        <Checkbox checked={selected} onClick={onSelectRow} />
      </TableCell>

      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <ListItemText
          primary={
            <Link href={`${paths.dashboard.user.root}/${guest.id}/edit`}>{guest.full_name}</Link>
          }
          secondary={guest.phone_number}
          primaryTypographyProps={{ typography: 'body2' }}
          secondaryTypographyProps={{ component: 'span', color: 'text.disabled' }}
        />
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <ListItemText
          primary={
            <Link href={`${paths.dashboard.user.root}/${host.id}/edit`}>{host.full_name}</Link>
          }
          secondary={host.phone_number}
          primaryTypographyProps={{ typography: 'body2' }}
          secondaryTypographyProps={{ component: 'span', color: 'text.disabled' }}
        />
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        {format(new Date(check_in), 'yyyy-MM-dd')}
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        {format(new Date(check_out), 'yyyy-MM-dd')}
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <ListItemText
          primary={format(new Date(created_at), 'yyyy-MM-dd')}
          secondary={format(new Date(created_at), 'h:mm a')}
          primaryTypographyProps={{ typography: 'body2' }}
          secondaryTypographyProps={{ component: 'span', color: 'text.disabled' }}
        />
      </TableCell>
      <TableCell sx={{ whiteSpace: 'wrap' }}>
        <Link href={`${paths.dashboard.listing.root}/${listing.id}`}>{listing.title}</Link>
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <Link href={`/booking/${id}/details`}>{reservation_code}</Link>
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>৳ {getDecimalValue(paid_amount)}</TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        {reviews.length > 0 ? (
          <Box>
            {reviews.map((r) => (
              <div key={r.id}>
                {r.is_guest_review ?
                  <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <div>
                        <strong>Rating:</strong> {r.rating}
                      </div>
                      <Iconify icon="eva:star-fill" sx={{ color: 'warning.main' }} />
                    </Box>
                    <div><strong>Review:</strong> {r?.review}</div>
                  </Box>
                  : <strong>No Review</strong>
                }
              </div>
            ))}
          </Box>
        ) : <strong>No Review</strong>}

      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        {reviews.length > 0 ? (
          <Box>
            {reviews.map((r) => (
              <div key={r.id}>
                {r.is_host_review ?
                  <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <div>
                        <strong>Rating:</strong> {r.rating}
                      </div>
                      <Iconify icon="eva:star-fill" sx={{ color: 'warning.main' }} />
                    </Box>
                    <div><strong>Type:</strong> {r?.review}</div>
                  </Box>
                  : <strong>No Review</strong>
                }
              </div>
            ))}
          </Box>
        ) : <strong>No Review</strong>}

      </TableCell>
      <TableCell sx={{ px: 1, whiteSpace: 'nowrap', display: 'flex', justifyContent: 'flex-center' }}>
        <Tooltip title="Quick Edit" placement="top" arrow>
          <Button
            color="primary"
            onClick={() => {
              router.push(`/booking/${id}/details`);
            }}
          >
            Details
          </Button>
        </Tooltip>
        {row.status === 'confirmed' && !isDuringStay && (
          <Tooltip title="Cancel Booking" placement="top" arrow>
            <Button
              color="error"
              onClick={onCancel}
            >
              Cancel
            </Button>
          </Tooltip>
        )}
      </TableCell>
    </TableRow>
  );
}
