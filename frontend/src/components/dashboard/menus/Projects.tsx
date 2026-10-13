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
import { Field, FieldGroup, FieldLabel } from "@/components/shadcn/field";
import { Input } from "@/components/shadcn/input";
import { ProjectCreateRequest } from "@/schemas/dashboard";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Plus } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import * as z from "zod";

export function ProjectCreateForm() {
  const [creatingProject, setCreatingProject] = useState<boolean>(false);

  const form = useForm<z.infer<typeof ProjectCreateRequest>>({
    resolver: zodResolver(ProjectCreateRequest),
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const onSubmit = async (data: z.infer<typeof ProjectCreateRequest>) => {
    setCreatingProject(true);
    console.log(data);
    const apiCall = new Promise((resolve) => {
      setTimeout(() => {
        resolve("success");
        // reject("failure")
      }, 1500);
    });

    apiCall.then((r) => {
      console.log(r);
      setCreatingProject(false);
    });
    // const request = new HttpRequest(`${API_URL}/projects/create`, {
    //     body: {
    //         name: data.name,
    //         descriptiom: data.description
    //     }
    // })

    // const [response, error] = await request.send(ProjectCreateResponse)

    // if (response) {
    //     toast.success(`Project '${response.name}' was successfully created!`)
    // }

    // if (error) {
    //     toast.error(error)
    // }
  };

  return (
    <Dialog>
      <form id="project-create-form" onSubmit={form.handleSubmit(onSubmit)}>
        <DialogTrigger asChild>
          <Button type="button" className="cursor-pointer">
            <Plus /> Create project
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create a new project</DialogTitle>
            <DialogDescription>Launch a new project</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Controller
              name="name"
              control={form.control}
              render={({ field }) => (
                <Field>
                  <FieldLabel>Name</FieldLabel>
                  <Input
                    {...field}
                    name="name"
                    type="text"
                    placeholder="Acme Corp"
                  />
                </Field>
              )}
            ></Controller>
            <Controller
              name="description"
              control={form.control}
              render={({ field }) => (
                <Field>
                  <FieldLabel>Description</FieldLabel>
                  <Input
                    {...field}
                    name="description"
                    type="text"
                    placeholder="Description about your project (summary of its purpose)..."
                  />
                </Field>
              )}
            ></Controller>
          </FieldGroup>
          <DialogFooter>
            <Button
              type="submit"
              form="project-create-form"
              className="cursor-pointer"
            >
              {creatingProject ? (
                <Loader2 className="animate-spin" />
              ) : (
                "Create"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </form>
    </Dialog>
  );
}

export function Projects() {
  return <></>;
}
