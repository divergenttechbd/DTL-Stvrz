// @mui
import Card from '@mui/material/Card';
import IconButton from '@mui/material/IconButton';
import Link from '@mui/material/Link';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
// routes
import { RouterLink } from 'src/routes/components';
import { paths } from 'src/routes/paths';
// utils
import { fCurrency } from 'src/utils/format-number';
import { fDateTime } from 'src/utils/format-time';
// types
import { IListingItem } from 'src/types/listing';
// components
import CustomPopover, { usePopover } from 'src/components/custom-popover';
import Iconify from 'src/components/iconify';
import Image from 'src/components/image';
import { useState } from 'react';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';

// ----------------------------------------------------------------------

type Props = {
  tour: IListingItem;
  onView: VoidFunction;
  onEdit: VoidFunction;
  onDelete: VoidFunction;
};

export default function TourItem({ tour, onView, onEdit, onDelete }: Props) {
  const popover = usePopover();

  // console.log('tour data', tour);

  const {
    id,
    title,
    price,
    images,
    cover_photo,
    created_at,
    address,
    owner,
    avg_rating,
    total_booking_count,
    status,
  } = tour;

  const [snackbarOpen, setSnackbarOpen] = useState(false);

  let listing_status;
  if (status === 'in_progress') {
    listing_status = 'In Progress';
  } else if (status === 'restricted') {
    listing_status = 'Restricted';
  } else if (status === 'published') {
    listing_status = 'Published';
  } else if (status === 'unpublished') {
    listing_status = 'Unpublished';
  }

  const renderRating = (
    <Stack
      direction="row"
      alignItems="center"
      sx={{
        top: 8,
        right: 8,
        zIndex: 9,
        borderRadius: 1,
        position: 'absolute',
        p: '2px 6px 2px 4px',
        typography: 'subtitle2',
        bgcolor: 'warning.lighter',
      }}
    >
      <Iconify icon="eva:star-fill" sx={{ color: 'warning.main', mr: 0.25 }} /> {avg_rating}
    </Stack>
  );

  const renderPrice = (
    <Stack
      direction="row"
      alignItems="center"
      sx={{
        top: 8,
        left: 8,
        zIndex: 9,
        borderRadius: 1,
        bgcolor: 'grey.800',
        position: 'absolute',
        p: '2px 6px 2px 4px',
        color: 'common.white',
        typography: 'subtitle2',
      }}
    >
      {fCurrency(price)}
    </Stack>
  );

  const renderImages = (
    <Stack
      spacing={0.5}
      direction="row"
      sx={{
        p: (theme) => theme.spacing(1, 1, 0, 1),
      }}
    >
      <Stack flexGrow={1} sx={{ position: 'relative' }}>
        {renderPrice}
        {renderRating}
        <Image alt={images[0]} src={cover_photo} sx={{ borderRadius: 1, height: 164, width: 1 }} />
      </Stack>
      <Stack spacing={0.5}>
        <Image alt={images[1]} src={images?.[1]} ratio="1/1" sx={{ borderRadius: 1, width: 80 }} />
        <Image alt={images[2]} src={images?.[2]} ratio="1/1" sx={{ borderRadius: 1, width: 80 }} />
      </Stack>
    </Stack>
  );

  const renderTexts = (
    <ListItemText
      sx={{
        p: (theme) => theme.spacing(2.5, 2.5, 2, 2.5),
      }}
      primary={`Posted date: ${fDateTime(created_at)}`}
      secondary={title}
      primaryTypographyProps={{
        typography: 'caption',
        color: 'text.disabled',
      }}
      secondaryTypographyProps={{
        mt: 1,
        noWrap: true,
        component: 'span',
        color: 'text.primary',
        typography: 'subtitle1',
      }}
    />
  );

  const renderInfo = (
    <Stack
      spacing={1.5}
      sx={{
        position: 'relative',
        p: (theme) => theme.spacing(0, 2.5, 2.5, 2.5),
      }}
    >
      <IconButton onClick={popover.onOpen} sx={{ position: 'absolute', bottom: 20, right: 8 }}>
        <Iconify icon="eva:more-vertical-fill" />
      </IconButton>

      {[
        {
          label: address || 'No location selected',
          icon: <Iconify icon="mingcute:location-fill" sx={{ color: 'error.main' }} />,
        },
        {
          label: (
            <Link sx={{ zIndex: 2 }} href={`${paths.dashboard.user.root}/${owner.id}/edit`}>
              {owner.full_name}
            </Link>
          ),
          icon: <Iconify icon="solar:flag-bold" sx={{ color: 'primary.main' }} />,
        },
        {
          label: `${listing_status}`,
          icon: <Iconify icon="mdi:list-status" sx={{ color: 'primary.main' }} />,
        },
        {
          label: `${total_booking_count} Booked`,
          icon: <Iconify icon="solar:users-group-rounded-bold" sx={{ color: 'primary.main' }} />,
        },
      ].map((item, idx) => (
        <Stack
          key={idx}
          spacing={1}
          direction="row"
          alignItems="center"
          sx={{ typography: 'body2' }}
        >
          {item.icon}
          {item.label}
        </Stack>
      ))}
    </Stack>
  );

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(
        `https://stayverz.divergenttechbd.com/rooms/${tour?.unique_id}`
      );
      setSnackbarOpen(true);
    } catch (err) {
      console.error('Failed to copy URL:', err);
    }
  };

  const handleSnackbarClose = (event?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }

    setSnackbarOpen(false);
  };

  return (
    <>
      <Card>
        <Link
          component={RouterLink}
          style={{ textDecoration: 'none' }}
          href={paths.dashboard.listing.details(id.toString())}
          color="inherit"
        >
          {renderImages}

          {renderTexts}
        </Link>

        {renderInfo}
      </Card>

      <CustomPopover
        open={popover.open}
        onClose={popover.onClose}
        arrow="right-top"
        sx={{ width: 140 }}
      >
        <MenuItem
          onClick={() => {
            popover.onClose();
            onView();
          }}
        >
          <Iconify icon="solar:eye-bold" />
          View
        </MenuItem>

        <MenuItem
          onClick={() => {
            popover.onClose();
            onEdit();
          }}
        >
          <Iconify icon="solar:pen-bold" />
          Edit
        </MenuItem>

        <MenuItem
          onClick={() => {
            popover.onClose();
            onDelete();
          }}
          sx={{ color: 'error.main' }}
        >
          <Iconify icon="solar:trash-bin-trash-bold" />
          Delete
        </MenuItem>
        {status === 'published' && (
          <MenuItem
            onClick={() => {
              handleCopy();
            }}
          >
            <Iconify icon="line-md:link" />
            Share
          </MenuItem>
        )}
      </CustomPopover>

      <Snackbar
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        open={snackbarOpen}
        autoHideDuration={3000}
        message=""
        onClose={handleSnackbarClose}
      >
        <Alert severity="success" variant="filled" sx={{ width: '100%' }}>
          Link Copied!
        </Alert>
      </Snackbar>
    </>
  );
}
