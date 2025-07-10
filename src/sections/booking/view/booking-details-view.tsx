import { useState, useCallback, useEffect } from 'react';
// @mui
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
// routes
import Iconify from 'src/components/iconify'
// components
import { useSettingsContext } from 'src/components/settings';
import { LoadingScreen } from 'src/components/loading-screen';
import { getBooking } from 'src/utils/queries/bookings';
import { IBookingItem } from 'src/types/booking';
import { RouterLink } from 'src/routes/components'
import { paths } from 'src/routes/paths'
import BookingDetailsContent from '../booking-details-content';
//

// ----------------------------------------------------------------------

const tabs = [{ value: 'content', label: 'Booking Content' }];

type Props = {
  id: string;
};

export default function BookingDetailsView({ id }: Props) {
  const settings = useSettingsContext();

  const [currentBooking, setCurrentBooking] = useState<IBookingItem | null>(null);

  const getBookingDetails = useCallback(async () => {
    try {
      const res = await getBooking(id);
      if(!res.success) throw res.data;
      setCurrentBooking(res.data);
    } catch(err) {
      console.log(err);
    }
  }, [id]);

  useEffect(() => {
    if(id) {
      getBookingDetails();
    }
  }, [getBookingDetails, id]);

  const [currentTab, setCurrentTab] = useState('content');

  const handleChangeTab = useCallback((event: React.SyntheticEvent, newValue: string) => {
    setCurrentTab(newValue);
  }, []);

  const renderTabs = (

    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: { xs: 3, md: 5 } }}>
      <Button
        component={RouterLink}
        href={paths.dashboard.booking.list}
        startIcon={<Iconify icon="eva:arrow-ios-back-fill" width={16} />}
      >
        Back
      </Button>

      <Tabs
        value={currentTab}
        onChange={handleChangeTab}
      >
        {tabs.map((tab) => (
          <Tab key={tab.value} iconPosition="end" value={tab.value} label={tab.label} />
        ))}
      </Tabs>
    </Box>

  );

  return currentBooking ? (
    <Container maxWidth={settings.themeStretch ? false : 'lg'}>
      {renderTabs}

      {currentTab === 'content' && <BookingDetailsContent booking={currentBooking} />}
    </Container>
  ) : (
    <LoadingScreen />
  );
}
