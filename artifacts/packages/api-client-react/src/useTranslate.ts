import { useMutation, type UseMutationOptions, type UseMutationResult } from "@tanstack/react-query";
import { translate, type TranslateMutationVariables, type TranslateResponse } from "./index";

/**
 * Generated-style mutation hook for POST /api/translate.
 *
 * Usage:
 *   const t = useTranslate({
 *     mutation: {
 *       onSuccess: (data) => console.log(data.translation),
 *       onError: (err) => console.error(err),
 *     },
 *   });
 *   t.mutate({ data: { text, source, target } });
 */
export function useTranslate(options?: {
  mutation?: Omit<
    UseMutationOptions<TranslateResponse, Error, TranslateMutationVariables>,
    "mutationFn"
  >;
}): UseMutationResult<TranslateResponse, Error, TranslateMutationVariables> {
  return useMutation<TranslateResponse, Error, TranslateMutationVariables>({
    mutationFn: translate,
    ...options?.mutation,
  });
}
