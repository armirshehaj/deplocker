import { Button } from "@/components/shadcn/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/shadcn/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/shadcn/field";
import { Input } from "@/components/shadcn/input";
import { enrolPasskey } from "@/lib/utils/auth";
import { PasskeyRegisterRequest } from "@/schemas/auth";
import { zodResolver } from "@hookform/resolvers/zod";
import { Fingerprint, Loader2 } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import * as z from "zod";

export function AddPasskeyForm({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState<boolean>(false);
  const [enrolling, setEnrolling] = useState<boolean>(false);

  const form = useForm<z.infer<typeof PasskeyRegisterRequest>>({
    resolver: zodResolver(PasskeyRegisterRequest),
    defaultValues: {
      name: "",
    },
  });

  const onSubmit = async (data: z.infer<typeof PasskeyRegisterRequest>) => {
    setEnrolling(true);
    await enrolPasskey(data.name);
    setEnrolling(false);
    setOpen(false);
    form.reset();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <form
          id="add-passkey-form"
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-6"
        >
          <DialogHeader>
            <DialogTitle>Add a passkey</DialogTitle>
            <DialogDescription>
              Sign in with your fingerprint, face or screen lock instead of a
              password.
            </DialogDescription>
          </DialogHeader>
          <Controller
            name="name"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field>
                <FieldLabel htmlFor="passkey-name">Name</FieldLabel>
                <Input
                  {...field}
                  id="passkey-name"
                  type="text"
                  placeholder="MacBook Touch ID"
                />
                <FieldDescription>
                  {fieldState.error?.message ??
                    "Names the device this passkey lives on, so you can remove the right one later."}
                </FieldDescription>
              </Field>
            )}
          />
          <DialogFooter>
            <Button
              type="submit"
              form="add-passkey-form"
              className="cursor-pointer"
            >
              {enrolling ? (
                <Loader2 className="animate-spin" />
              ) : (
                <>
                  <Fingerprint /> Create passkey
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
