import axios from '../axios'

export const getListings: any = async (data: any) => {
  const endpoint = '/listings/admin/listings/';
  return axios.get<any>(endpoint, { params: data });
};

export const getListingsLite: any = async (data: any) => {
  const endpoint = '/listings/admin/lite-listings/';
  return axios.get<any>(endpoint, { params: data });
};

export const getListingCategories: any = async () => {
  const endpoint = '/listings/admin/categories/';
  return axios.get<any>(endpoint);
};

export const getListing: any = async (id: number) => {
  const endpoint = `/listings/admin/listings/${id}/`;
  return axios.get<any>(endpoint);
};

export const updateListing: any = async (data: any) => {
  const endpoint = `/listings/admin/listings/${data.id}/`;
  return axios.patch(endpoint, data);
};
export const softDeleteListing: any = async (data: any) => {
  const endpoint = `/listings/admin/listings/${data.id}`;
  return axios.delete(endpoint, data);
};
export const updateInstantBookingListing: any = async (data: any) => {
  const endpoint = `/listings/admin/listings/${data.id}/`;
  return axios.put(endpoint, data);
};
export const getDistrictPoints: any = async (data: any) => {
  const endpoint = "/maps/get-district-points/";
  return axios.get<any>(endpoint, { params: data });
};

export const getSubDistrictPoints: any = async (data: any) => {
  const endpoint = `/maps/api/sub-districts-by-district/?district_name=${data.q}`;
  return axios.get<any>(endpoint);
};
