import axios, { AxiosRequestConfig } from 'axios'
import { ChatResponse, Response } from '~/lib/api/types'
import { getToken } from '~/lib/storage/token'

export const axiosApiInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL
})

export const axiosChatApiInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_CHAT_API_URL
})

export const axiosTokenApiInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL
})

export const tokenApiClient = async <T=any>(requestConfig: AxiosRequestConfig & {endpoint: string}): Promise<Response<T>> => {
  const { endpoint, ...configs } = requestConfig
  const token = getToken()
  try {
    const response = await axiosTokenApiInstance.request({
      url: `/${requestConfig.endpoint}`,
      ...configs,
      headers: { ...token && { Authorization: `Bearer ${token}` }, ...configs.headers }
    })

    return {
      code: response.status,
      isSucceed: true,
      data: (response.data.data ? response.data.data : response.data) as T,
      error: response.statusText,
      message: response.data.message,
      meta: response.data?.meta_data,
      stats: response.data?.stats
    }
  } catch (e) {
    const error = e as any
    throw {
      code: error.response?.status || 503,
      isSucceed: false,
      data: undefined,
      error: typeof error.response?.data === 'string' ? 'Something went wrong' : error.response?.data?.message instanceof Array ? error?.response.data.message.toString() : error?.response.data.message,
    } as T
  }
}

export const apiClient = async <T=any>(requestConfig: AxiosRequestConfig & {endpoint: string}): Promise<Response<T>> => {
  const { endpoint, ...configs } = requestConfig
  const token = getToken()
  try {
    const response = await axiosApiInstance.request({
      url: `/${requestConfig.endpoint}`,
      ...configs,
      headers: { ...token && { Authorization: `Bearer ${token}` }, ...configs.headers }
    })

    return {
      code: response.status,
      isSucceed: true,
      data: (response.data.data ? response.data.data : response.data) as T,
      error: response.statusText,
      message: response.data.message,
      meta: response.data?.meta_data,
      stats: response.data?.stats
    }
  } catch (e) {
    const error = e as any
    throw {
      code: error.response?.status || 503,
      isSucceed: false,
      data: undefined,
      error: typeof error.response?.data === 'string' ? 'Something went wrong' : error.response?.data?.message instanceof Array ? error?.response.data.message.toString() : error?.response.data.message,
    } as T
  }
}

export const chatApiClient = async <T=any, K=any>(requestConfig: AxiosRequestConfig & {endpoint: string}): Promise<ChatResponse<T, K>> => {
  const { endpoint, ...configs } = requestConfig
  const token = getToken()
  try {
    const response = await axiosChatApiInstance.request({
      url: `${process.env.NEXT_PUBLIC_CHAT_API_URL}/${requestConfig.endpoint}`,
      ...configs,
      headers: { ...token && { Authorization: `Bearer ${token}` }, ...configs.headers }
    })

    return {
      code: response.status,
      isSucceed: true,
      data: (response.data.data ? response.data.data : response.data) as T,
      extra_data: (response.data.extra_data ? response.data.extra_data : response.data) as K,
      error: response.statusText,
      message: response.data.message,
      meta: response.data?.meta_data
    }
  } catch (e) {
    const error = e as any
    throw {
      code: error.response?.status || 503,
      isSucceed: false,
      data: undefined,
      error: typeof error.response?.data === 'string' ? 'Something went wrong' : error.response?.data?.message instanceof Array ? error?.response.data.message.toString() : error?.response.data.message,
    }
  }
}
