// @mui
import Container from '@mui/material/Container'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button'
// routes
import { paths } from 'src/routes/paths'
// _mock
import CustomBreadcrumbs from 'src/components/custom-breadcrumbs'
import { useSettingsContext } from 'src/components/settings'
//
import { useCallback, useEffect, useState } from 'react'
import { RouterLink } from 'src/routes/components'
import Iconify from 'src/components/iconify'
import { useTabs } from 'src/hooks/use-tabs'
import { BookingListView } from 'src/sections/booking/view'
import { TourListView } from 'src/sections/listing/view'
import { PayoutListView } from 'src/sections/payout/view'
import ReviewListView from 'src/sections/review/view/review-list-view'
import HostPaymentMethods from 'src/sections/user/host-payment-methods'
import { ITabs, IUserItem } from 'src/types/user'
import { getUser } from 'src/utils/queries/users'
import UserNewEditForm from '../user-new-edit-form'

// ----------------------------------------------------------------------

type Props = {
  id: string;
};

export default function UserEditView({ id }: Props) {
  const settings = useSettingsContext();
  const [currentUser, setCurrentUser] = useState<IUserItem>();
  const [userType, setUserType] = useState<string>('')

  // profile details
  const getUserDetails = useCallback(async () => {
    try {
      const res = await getUser(id);
      if(!res.success) throw res.data;
      setCurrentUser(res.data);
      setUserType(res.data?.u_type)
    } catch(err) {
      console.log(err);
    }
  }, [id]);

  useEffect(() => {
    if(id) {
      getUserDetails();
    }
  }, [getUserDetails, id]);

  // Tabs
  const tabs = useTabs('profile');
  const TABS: ITabs = [
    {
      value: 'profile',
      label: 'Profile',
      icon: <Iconify icon="solar:user-id-bold" width={24} />,
    },
    {
      value: 'listings',
      label: 'Listings',
      icon: <Iconify icon="solar:bill-list-bold" width={24} />,
    },
    {
      value: 'bookings',
      label: 'Bookings',
      icon: <Iconify icon="solar:bell-bing-bold" width={24} />,
    },
    {
      value: 'reviews',
      label: 'Reviews',
      icon: <Iconify icon="material-symbols-light:rate-review-sharp" width={24} />,
    },
    {
      value: 'payouts',
      label: 'Payouts',
      icon: <Iconify icon="tdesign:undertake-transaction" width={24} />,
    },
    {
      value: 'payment-methods',
      label: 'Payment Methods',
      icon: <Iconify icon="ic:round-vpn-key" width={24} />,
    },
  ];

  return (
    <Container maxWidth={settings.themeStretch ? false : 'lg'}>
      <Button
        component={RouterLink}
        href={paths.dashboard.user.list}
        startIcon={<Iconify icon="eva:arrow-ios-back-fill" width={16} />}
        sx={{ mb: 2 }}
      >
        Back
      </Button>

      <CustomBreadcrumbs
        heading="Edit"
        links={[
          {
            name: 'Dashboard',
            href: paths.dashboard.root,
          },
          {
            name: 'User List',
            href: paths.dashboard.user.list,
          },
          { name: 'User Details' },
        ]}
        sx={{
          mb: { xs: 3, md: 5 },
        }}
      />

      <Tabs value={tabs.value} onChange={tabs.onChange} sx={{ mb: { xs: 3, md: 5 } }}>
        {TABS.map((tab) => {
          if(userType === 'guest' && (tab.value === 'payouts' || tab.value === 'payment-methods' || tab.value === 'listings')) {
            return ''
          }
          return <Tab key={tab.value} label={tab.label} icon={tab.icon} value={tab.value} />

        })}
      </Tabs>

      {tabs.value === 'profile' && (
        <UserNewEditForm currentUser={currentUser} getUserDetails={getUserDetails} />
      )}
      {tabs.value === 'listings' && (
        <TourListView
          fromUserDetails
          userId={Number(id)}
        />
      )}
      {tabs.value === 'bookings' && (
        <BookingListView
          fromUserDetails
          userType={userType}
          userId={Number(id)}
        />
      )}
      {tabs.value === 'reviews' && (
        <ReviewListView
          fromUserDetails
          userType={userType}
          userId={Number(id)}
        />
      )}
      {tabs.value === 'payouts' && (
        <PayoutListView
          fromUserDetails
          userId={Number(id)}
        />
      )}
      {tabs.value === 'payment-methods' && (
        <HostPaymentMethods id={Number(id)} />
      )}
    </Container>
  );
}
